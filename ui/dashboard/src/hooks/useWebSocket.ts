import { useEffect, useRef, useCallback, useState } from 'react'

export type WSStatus = 'connecting' | 'connected' | 'disconnected'

type WSMessage =
  | { type: 'new_signal'; data: unknown }
  | { type: 'signal_update'; data: unknown }
  | { type: 'snapshot'; signals: unknown[] }
  | { type: 'ping' }

interface UseWebSocketOptions {
  url: string
  enabled: boolean
  onNewSignal: (signal: unknown) => void
  onSignalUpdate: (signal: unknown) => void
}

const BASE_DELAY = 1000
const MAX_DELAY = 30000

export function useWebSocket({ url, enabled, onNewSignal, onSignalUpdate }: UseWebSocketOptions) {
  const [status, setStatus] = useState<WSStatus>('disconnected')
  const wsRef = useRef<WebSocket | null>(null)
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const attemptsRef = useRef(0)
  const mountedRef = useRef(true)

  const cleanup = useCallback(() => {
    if (retryRef.current) {
      clearTimeout(retryRef.current)
      retryRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.onopen = null
      wsRef.current.onmessage = null
      wsRef.current.onerror = null
      wsRef.current.onclose = null
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  const connect = useCallback(() => {
    if (!mountedRef.current || !enabled) return

    cleanup()
    setStatus('connecting')

    let ws: WebSocket
    try {
      ws = new WebSocket(url)
    } catch {
      scheduleReconnect()
      return
    }

    wsRef.current = ws

    ws.onopen = () => {
      if (!mountedRef.current) return
      attemptsRef.current = 0
      setStatus('connected')
    }

    ws.onmessage = (event) => {
      if (!mountedRef.current) return
      try {
        const msg: WSMessage = JSON.parse(event.data as string)
        if (msg.type === 'new_signal') onNewSignal(msg.data)
        else if (msg.type === 'signal_update') onSignalUpdate(msg.data)
        else if (msg.type === 'snapshot') msg.signals.forEach(s => onNewSignal(s))
      } catch {
        // ignore malformed messages
      }
    }

    ws.onerror = () => {
      // handled in onclose
    }

    ws.onclose = () => {
      if (!mountedRef.current) return
      setStatus('disconnected')
      scheduleReconnect()
    }
  }, [url, enabled, onNewSignal, onSignalUpdate, cleanup]) // eslint-disable-line

  const scheduleReconnect = useCallback(() => {
    if (!mountedRef.current || !enabled) return
    const delay = Math.min(BASE_DELAY * 2 ** attemptsRef.current, MAX_DELAY)
    attemptsRef.current += 1
    retryRef.current = setTimeout(connect, delay)
  }, [enabled, connect])

  useEffect(() => {
    mountedRef.current = true
    if (enabled) connect()
    return () => {
      mountedRef.current = false
      cleanup()
    }
  }, [enabled]) // eslint-disable-line

  return { status }
}
