import type { Signal, Stats } from '../types/signal'
import { formatRR } from '../utils/formatters'

interface Props {
  signals: Signal[]
  stats: Stats | null
}

export function StatsBar({ signals, stats }: Props) {
  const activeSignals = signals.filter(s => s.status === 'active')
  const longCount = activeSignals.filter(s => s.direction === 'long').length
  const shortCount = activeSignals.filter(s => s.direction === 'short').length
  const highestScore = activeSignals.length ? Math.max(...activeSignals.map(s => s.score)) : 0
  const avgRR =
    activeSignals.length
      ? activeSignals.reduce((sum, s) => sum + s.rr_ratio, 0) / activeSignals.length
      : 0

  const totalToday = stats?.total_signals_today ?? 0
  const activeCount = stats?.active_signals ?? activeSignals.length
  const biasPct = activeCount > 0 ? (longCount / activeCount) * 100 : 50

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Today's Signals */}
        <div className="bg-slate-800 rounded-xl border border-slate-700/60 p-4 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sky-400/10 text-sky-400 flex items-center justify-center flex-shrink-0">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"
              />
            </svg>
          </div>
          <div>
            <div className="text-2xl font-bold tabular-nums font-price text-sky-400">
              {totalToday || '—'}
            </div>
            <div className="text-xs text-slate-500">Today's Signals</div>
          </div>
        </div>

        {/* Active Signals */}
        <div className="bg-slate-800 rounded-xl border border-slate-700/60 p-4 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-emerald-400/10 text-emerald-400 flex items-center justify-center flex-shrink-0">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z"
              />
            </svg>
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-2xl font-bold tabular-nums font-price text-emerald-400">
              {activeCount}
            </div>
            <div className="text-xs text-slate-500">Active Now</div>
          </div>
          {activeCount > 0 && (
            <div className="text-right text-xs leading-tight flex-shrink-0">
              <div className="text-emerald-400 font-semibold font-price">{longCount}L</div>
              <div className="text-rose-400 font-semibold font-price">{shortCount}S</div>
            </div>
          )}
        </div>

        {/* Highest Score */}
        <div className="bg-slate-800 rounded-xl border border-slate-700/60 p-4 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-amber-400/10 text-amber-400 flex items-center justify-center flex-shrink-0">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z"
              />
            </svg>
          </div>
          <div>
            <div className="text-2xl font-bold tabular-nums font-price text-amber-400">
              {highestScore > 0 ? highestScore : '—'}
            </div>
            <div className="text-xs text-slate-500">Best Score</div>
          </div>
        </div>

        {/* Average R:R */}
        <div className="bg-slate-800 rounded-xl border border-slate-700/60 p-4 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-violet-400/10 text-violet-400 flex items-center justify-center flex-shrink-0">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M7.5 14.25v2.25m3-4.5v4.5m3-6.75v6.75m3-9v9M6 20.25h12A2.25 2.25 0 0020.25 18V6A2.25 2.25 0 0018 3.75H6A2.25 2.25 0 003.75 6v12A2.25 2.25 0 006 20.25z"
              />
            </svg>
          </div>
          <div>
            <div className="text-2xl font-bold tabular-nums font-price text-violet-400">
              {avgRR > 0 ? formatRR(avgRR) : '—'}
            </div>
            <div className="text-xs text-slate-500">Avg R:R</div>
          </div>
        </div>
      </div>

      {/* Market bias bar */}
      {activeCount > 0 && (
        <div className="bg-slate-800/60 rounded-xl border border-slate-700/40 px-4 py-2.5 flex items-center gap-4">
          <span className="text-xs text-slate-500 flex-shrink-0 w-20">Market Bias</span>
          <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 rounded-full transition-all duration-700"
              style={{ width: `${biasPct}%` }}
            />
          </div>
          <div className="flex items-center gap-3 text-xs flex-shrink-0">
            <span className="text-emerald-400 font-semibold font-price">{longCount} Long</span>
            <span className="text-slate-700">·</span>
            <span className="text-rose-400 font-semibold font-price">{shortCount} Short</span>
          </div>
        </div>
      )}
    </div>
  )
}
