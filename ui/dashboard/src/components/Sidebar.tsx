import { useMemo } from 'react'
import type { Signal, Stats, FilterState } from '../types/signal'

interface Props {
  signals: Signal[]
  stats: Stats | null
  filters: FilterState
  onFilterChange: (f: FilterState) => void
}

// v2.0 — min_score is 65
const SCORE_THRESHOLDS = [0, 65, 70, 80, 90] as const

export function Sidebar({ signals, stats, filters, onFilterChange }: Props) {
  const update = (patch: Partial<FilterState>) => onFilterChange({ ...filters, ...patch })

  const activeSignals = useMemo(() => signals.filter(s => s.status === 'active'), [signals])

  const scenarios = useMemo(
    () => [...new Set(signals.map(s => s.scenario_name))].sort(),
    [signals],
  )

  const symbolCounts = useMemo(() => {
    const counts: Record<string, { total: number; long: number; short: number }> = {}
    for (const s of activeSignals) {
      if (!counts[s.symbol]) counts[s.symbol] = { total: 0, long: 0, short: 0 }
      counts[s.symbol].total++
      counts[s.symbol][s.direction]++
    }
    return counts
  }, [activeSignals])

  const sortedSymbols = Object.entries(symbolCounts).sort((a, b) => b[1].total - a[1].total)

  const hasFilters =
    filters.symbol !== '' ||
    filters.direction !== '' ||
    filters.scenario !== '' ||
    filters.minScore > 0

  return (
    <div className="p-4 space-y-5 min-w-[256px]">
      {/* Header */}
      <div className="flex items-center justify-between pt-1">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Filters</span>
        {hasFilters && (
          <button
            onClick={() =>
              onFilterChange({ symbol: '', direction: '', scenario: '', minScore: 0, sortBy: filters.sortBy })
            }
            className="text-xs text-slate-600 hover:text-slate-400 transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      {/* Direction */}
      <div>
        <div className="text-[10px] font-semibold text-slate-600 uppercase tracking-wider mb-2">Direction</div>
        <div className="flex gap-1.5">
          {(['', 'long', 'short'] as const).map(dir => (
            <button
              key={dir || 'all'}
              onClick={() => update({ direction: dir })}
              className={`flex-1 py-1.5 text-xs font-semibold rounded-lg border transition-all ${
                filters.direction === dir
                  ? dir === 'long'
                    ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
                    : dir === 'short'
                    ? 'bg-rose-500/20 text-rose-400 border-rose-500/40'
                    : 'bg-slate-600/50 text-slate-200 border-slate-500/60'
                  : 'bg-slate-800 text-slate-500 border-slate-700 hover:border-slate-500 hover:text-slate-300'
              }`}
            >
              {dir === '' ? 'All' : dir === 'long' ? '▲ L' : '▼ S'}
            </button>
          ))}
        </div>
      </div>

      {/* Min Score */}
      <div>
        <div className="text-[10px] font-semibold text-slate-600 uppercase tracking-wider mb-2">Min Score</div>
        <div className="flex gap-1 flex-wrap">
          {SCORE_THRESHOLDS.map(threshold => (
            <button
              key={threshold}
              onClick={() => update({ minScore: threshold })}
              className={`px-2.5 py-1 text-xs font-semibold rounded-lg border transition-all ${
                filters.minScore === threshold
                  ? 'bg-amber-500/20 text-amber-400 border-amber-500/40'
                  : 'bg-slate-800 text-slate-500 border-slate-700 hover:border-slate-500 hover:text-slate-300'
              }`}
            >
              {threshold === 0 ? 'All' : `${threshold}+`}
            </button>
          ))}
        </div>
      </div>

      {/* Sort By */}
      <div>
        <div className="text-[10px] font-semibold text-slate-600 uppercase tracking-wider mb-2">Sort By</div>
        <div className="flex gap-1.5">
          {(['score', 'time', 'rr'] as const).map(sort => (
            <button
              key={sort}
              onClick={() => update({ sortBy: sort })}
              className={`flex-1 py-1.5 text-xs font-semibold rounded-lg border transition-all ${
                filters.sortBy === sort
                  ? 'bg-violet-500/20 text-violet-400 border-violet-500/40'
                  : 'bg-slate-800 text-slate-500 border-slate-700 hover:border-slate-500 hover:text-slate-300'
              }`}
            >
              {sort === 'score' ? 'Score' : sort === 'time' ? 'Time' : 'R:R'}
            </button>
          ))}
        </div>
      </div>

      {/* Divider */}
      <div className="border-t border-slate-700/40" />

      {/* Scenario filter */}
      {scenarios.length > 0 && (
        <div>
          <div className="text-[10px] font-semibold text-slate-600 uppercase tracking-wider mb-2">Scenario</div>
          <div className="space-y-0.5">
            <button
              onClick={() => update({ scenario: '' })}
              className={`w-full text-left px-2.5 py-1.5 text-xs rounded-lg transition-all ${
                filters.scenario === ''
                  ? 'bg-slate-700/70 text-slate-200'
                  : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300'
              }`}
            >
              All Scenarios
            </button>
            {scenarios.map(sc => (
              <button
                key={sc}
                onClick={() => update({ scenario: sc === filters.scenario ? '' : sc })}
                className={`w-full text-left px-2.5 py-1.5 text-xs rounded-lg transition-all flex items-center justify-between gap-2 ${
                  filters.scenario === sc
                    ? 'bg-blue-500/15 text-blue-400'
                    : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300'
                }`}
              >
                <span className="truncate">{sc}</span>
                {stats?.scenarios[sc] && (
                  <span className="text-slate-600 flex-shrink-0 tabular-nums">
                    {stats.scenarios[sc].count}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Symbol watchlist */}
      {sortedSymbols.length > 0 && (
        <div>
          <div className="text-[10px] font-semibold text-slate-600 uppercase tracking-wider mb-2">
            Active Symbols
          </div>
          <div className="space-y-0.5">
            <button
              onClick={() => update({ symbol: '' })}
              className={`w-full text-left px-2.5 py-1.5 text-xs rounded-lg transition-all ${
                filters.symbol === ''
                  ? 'bg-slate-700/70 text-slate-200'
                  : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300'
              }`}
            >
              All Symbols
            </button>
            {sortedSymbols.map(([symbol, counts]) => (
              <button
                key={symbol}
                onClick={() => update({ symbol: symbol === filters.symbol ? '' : symbol })}
                className={`w-full text-left px-2.5 py-1.5 text-xs rounded-lg transition-all flex items-center justify-between gap-2 ${
                  filters.symbol === symbol
                    ? 'bg-sky-500/15 text-sky-400'
                    : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300'
                }`}
              >
                <span className="font-price font-medium">{symbol.replace('/USDT', '')}</span>
                <div className="flex items-center gap-1.5 flex-shrink-0">
                  {counts.long > 0 && (
                    <span className="text-emerald-400/80 text-[10px]">▲{counts.long}</span>
                  )}
                  {counts.short > 0 && (
                    <span className="text-rose-400/80 text-[10px]">▼{counts.short}</span>
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
