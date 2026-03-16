import { useState, useMemo } from 'react'
import type { Signal } from '../types/signal'
import {
  formatTimeAgo,
  formatRR,
  formatScore,
  statusLabel,
  statusColor,
  trendColor,
  alertTypeEmoji,
} from '../utils/formatters'

interface Props {
  history: Signal[]
}

const ALL = '__all__'

export function HistoryTable({ history }: Props) {
  const [symbolFilter, setSymbolFilter] = useState(ALL)
  const [scenarioFilter, setScenarioFilter] = useState(ALL)
  const [dirFilter, setDirFilter] = useState<'' | 'long' | 'short'>('')

  const symbols = useMemo(() => [...new Set(history.map(s => s.symbol))].sort(), [history])
  const scenarios = useMemo(
    () => [...new Set(history.map(s => s.scenario_name))].sort(),
    [history],
  )

  const filtered = useMemo(() => {
    return history
      .filter(s => symbolFilter === ALL || s.symbol === symbolFilter)
      .filter(s => scenarioFilter === ALL || s.scenario_name === scenarioFilter)
      .filter(s => !dirFilter || s.direction === dirFilter)
      .slice(0, 50)
  }, [history, symbolFilter, scenarioFilter, dirFilter])

  const hasFilters = symbolFilter !== ALL || scenarioFilter !== ALL || dirFilter !== ''

  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700/60 p-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-slate-300">Signal History</h3>
          <span className="text-xs text-slate-600 font-price tabular-nums">
            {filtered.length}/{history.length}
          </span>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {/* Direction pills */}
          <div className="flex gap-1">
            {(['', 'long', 'short'] as const).map(d => (
              <button
                key={d || 'all'}
                onClick={() => setDirFilter(d)}
                className={`px-2 py-1 text-[11px] font-semibold rounded-lg border transition-all ${
                  dirFilter === d
                    ? d === 'long'
                      ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
                      : d === 'short'
                      ? 'bg-rose-500/20 text-rose-400 border-rose-500/40'
                      : 'bg-slate-600/50 text-slate-200 border-slate-500/60'
                    : 'bg-slate-700/50 text-slate-500 border-slate-700 hover:border-slate-500 hover:text-slate-300'
                }`}
              >
                {d === '' ? 'All' : d === 'long' ? '▲' : '▼'}
              </button>
            ))}
          </div>

          <select
            value={symbolFilter}
            onChange={e => setSymbolFilter(e.target.value)}
            className="bg-slate-700 border border-slate-600 text-slate-300 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-slate-500"
          >
            <option value={ALL}>All Symbols</option>
            {symbols.map(s => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>

          <select
            value={scenarioFilter}
            onChange={e => setScenarioFilter(e.target.value)}
            className="bg-slate-700 border border-slate-600 text-slate-300 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-slate-500"
          >
            <option value={ALL}>All Scenarios</option>
            {scenarios.map(s => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>

          {hasFilters && (
            <button
              onClick={() => {
                setSymbolFilter(ALL)
                setScenarioFilter(ALL)
                setDirFilter('')
              }}
              className="text-xs text-slate-600 hover:text-slate-400 transition-colors"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-slate-700/60">
              <th className="text-left py-2 px-3 font-medium text-slate-500 whitespace-nowrap">Time</th>
              <th className="text-left py-2 px-3 font-medium text-slate-500">Symbol</th>
              <th className="text-left py-2 px-3 font-medium text-slate-500 hidden sm:table-cell">
                Type
              </th>
              <th className="text-left py-2 px-3 font-medium text-slate-500 hidden md:table-cell">
                HTF
              </th>
              <th className="text-left py-2 px-3 font-medium text-slate-500">Dir</th>
              <th className="text-right py-2 px-3 font-medium text-slate-500">Score</th>
              <th className="text-right py-2 px-3 font-medium text-slate-500">R:R</th>
              <th className="text-left py-2 px-3 font-medium text-slate-500">Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-12 text-center text-slate-600">
                  No signals match the current filters
                </td>
              </tr>
            ) : (
              filtered.map((signal, i) => (
                <tr
                  key={signal.id}
                  className={`${
                    i !== filtered.length - 1 ? 'border-b border-slate-700/20' : ''
                  } hover:bg-slate-700/20 transition-colors`}
                >
                  <td className="py-2.5 px-3 text-slate-500 whitespace-nowrap tabular-nums font-price">
                    {formatTimeAgo(signal.timestamp)}
                  </td>
                  <td className="py-2.5 px-3 whitespace-nowrap">
                    <span className="font-price font-semibold text-slate-200">
                      {signal.symbol.replace('/USDT', '')}
                    </span>
                    <span className="text-slate-600">/USDT</span>
                  </td>
                  <td className="py-2.5 px-3 hidden sm:table-cell">
                    <span className="text-slate-400 flex items-center gap-1">
                      <span>{alertTypeEmoji(signal.alert_type)}</span>
                      <span className="truncate max-w-[120px]">{signal.alert_type || signal.scenario_name}</span>
                    </span>
                  </td>
                  <td className="py-2.5 px-3 hidden md:table-cell">
                    <span className={`font-price text-[10px] capitalize ${trendColor(signal.htf_trend)}`}>
                      {signal.htf_trend || '—'}
                    </span>
                  </td>
                  <td className="py-2.5 px-3">
                    <span
                      className={`font-semibold text-[11px] ${
                        signal.direction === 'long' ? 'text-emerald-400' : 'text-rose-400'
                      }`}
                    >
                      {signal.direction === 'long' ? '▲ L' : '▼ S'}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    <span
                      className={`font-price tabular-nums font-bold ${
                        signal.score >= 80
                          ? 'text-emerald-400'
                          : signal.score >= 65
                          ? 'text-amber-400'
                          : 'text-rose-400'
                      }`}
                    >
                      {formatScore(signal.score)}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-right font-price tabular-nums text-violet-400">
                    {formatRR(signal.rr_ratio)}
                  </td>
                  <td className="py-2.5 px-3">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] ${statusColor(signal.status)}`}>
                      {statusLabel(signal.status)}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
