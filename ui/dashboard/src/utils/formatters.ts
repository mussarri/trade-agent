import { formatDistanceToNow, parseISO } from 'date-fns'
import type { SignalStatus } from '../types/signal'

function asFiniteNumber(value: number | null | undefined): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

export function formatPrice(value: number): string {
  if (value >= 10000) {
    return value.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
  }
  if (value >= 1000) {
    return value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }
  return value.toLocaleString('en-US', { minimumFractionDigits: 3, maximumFractionDigits: 3 })
}

export function formatRR(rr: number | null | undefined): string {
  const n = asFiniteNumber(rr)
  if (n === null) return '—'
  return `1:${n.toFixed(1)}`
}

export function formatScore(score: number | null | undefined): string {
  const n = asFiniteNumber(score)
  if (n === null) return '—'
  return n.toFixed(0)
}

export function formatTimeAgo(isoString: string): string {
  try {
    return formatDistanceToNow(parseISO(isoString), { addSuffix: true })
  } catch {
    return isoString
  }
}

export function formatUTCTime(date: Date): string {
  return date.toISOString().slice(11, 19) + ' UTC'
}

// v2.0 — min_score is now 65
export function scoreColor(score: number): string {
  if (score >= 80) return 'text-emerald-400'
  if (score >= 65) return 'text-amber-400'
  return 'text-rose-400'
}

export function scoreBarColor(score: number): string {
  if (score >= 80) return 'bg-emerald-500'
  if (score >= 65) return 'bg-amber-500'
  return 'bg-rose-500'
}

export function statusLabel(status: SignalStatus): string {
  if (status === 'active') return 'Active'
  return status
}

export function statusColor(status: SignalStatus): string {
  if (status === 'active') return 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
  return 'bg-slate-700/40 text-slate-500 border border-slate-600/30'
}

export function sessionLabel(session: string): string {
  const map: Record<string, string> = {
    london:   '🇬🇧 London',
    new_york: '🇺🇸 New York',
    overlap:  '🔀 Overlap',
    asian:    '🌏 Asian',
    off:      '💤 Off',
  }
  return map[session] ?? session
}

export function trendColor(trend: string): string {
  if (trend === 'bullish') return 'text-emerald-400'
  if (trend === 'bearish') return 'text-rose-400'
  return 'text-slate-500'
}

export function alertTypeEmoji(alertType: string): string {
  const map: Record<string, string> = {
    SETUP_DETECTED: '👀',
    ENTRY_CONFIRMED: '✅',
  }
  return map[alertType] ?? '🔔'
}
