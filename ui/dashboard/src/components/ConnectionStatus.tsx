import type { WSStatus } from '../hooks/useWebSocket'

interface Props {
  status: WSStatus
  isMock: boolean
}

export function ConnectionStatus({ status, isMock }: Props) {
  if (isMock) {
    return (
      <div className="flex items-center gap-2 text-xs text-amber-400">
        <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse-dot" />
        <span>MOCK</span>
      </div>
    )
  }

  const config = {
    connected: {
      dot: 'bg-emerald-400 animate-pulse-dot',
      text: 'text-emerald-400',
      label: 'Live',
    },
    connecting: {
      dot: 'bg-amber-400 animate-pulse',
      text: 'text-amber-400',
      label: 'Connecting…',
    },
    disconnected: {
      dot: 'bg-rose-500',
      text: 'text-rose-400',
      label: 'Disconnected',
    },
  }[status]

  return (
    <div className={`flex items-center gap-2 text-xs ${config.text}`}>
      <span className={`w-2 h-2 rounded-full ${config.dot}`} />
      <span>{config.label}</span>
    </div>
  )
}
