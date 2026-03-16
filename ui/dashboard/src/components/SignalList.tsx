import { useRef, useEffect, useState } from 'react'
import type { Signal } from '../types/signal'
import { SignalCard } from './SignalCard'

interface Props {
  signals: Signal[]
}

export function SignalList({ signals }: Props) {
  const prevCountRef = useRef(signals.length)
  const [newIds, setNewIds] = useState<Set<string>>(new Set())

  useEffect(() => {
    if (signals.length > prevCountRef.current) {
      const latest = signals[0]
      if (latest) {
        setNewIds(prev => new Set([...prev, latest.id]))
        setTimeout(() => {
          setNewIds(prev => {
            const next = new Set(prev)
            next.delete(latest.id)
            return next
          })
        }, 2000)
      }
    }
    prevCountRef.current = signals.length
  }, [signals.length]) // eslint-disable-line

  const longCount = signals.filter(s => s.direction === 'long').length
  const shortCount = signals.filter(s => s.direction === 'short').length

  return (
    <div>
      {/* Section header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Active Signals</h2>
          <span className="text-xs px-2 py-0.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-full tabular-nums font-price">
            {signals.length}
          </span>
        </div>
        {signals.length > 0 && (
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span className="text-emerald-400/70">▲ {longCount}</span>
            <span className="text-slate-700">·</span>
            <span className="text-rose-400/70">▼ {shortCount}</span>
          </div>
        )}
      </div>

      {signals.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center bg-slate-800/30 rounded-xl border border-slate-700/30">
          <div className="w-14 h-14 rounded-2xl bg-slate-800 border border-slate-700 flex items-center justify-center mb-4">
            <svg
              className="w-7 h-7 text-slate-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z"
              />
            </svg>
          </div>
          <p className="text-slate-400 font-medium">No active signals</p>
          <p className="text-slate-600 text-sm mt-1">Waiting for market structure to align…</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {signals.map(signal => (
            <SignalCard key={signal.id} signal={signal} isNew={newIds.has(signal.id)} />
          ))}
        </div>
      )}
    </div>
  )
}
