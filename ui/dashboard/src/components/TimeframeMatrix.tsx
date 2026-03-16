import { useMemo } from 'react'
import type { Signal } from '../types/signal'
import { scoreColor } from '../utils/formatters'

interface Props {
  signals: Signal[]
}

export function TimeframeMatrix({ signals }: Props) {
  const { symbols, tfPairs, matrix } = useMemo(() => {
    const syms = [...new Set(signals.map(s => s.symbol))].sort()
    const pairs = [
      ...new Set(
        signals
          .map(s => `${s.timeframe_htf}/${s.timeframe_ltf}`)
          .filter(p => p !== '/'),
      ),
    ].sort()

    const mat: Record<string, Record<string, Signal | undefined>> = {}
    for (const sym of syms) {
      mat[sym] = {}
      for (const pair of pairs) {
        const [htf, ltf] = pair.split('/')
        mat[sym][pair] = signals.find(
          s => s.symbol === sym && s.timeframe_htf === htf && s.timeframe_ltf === ltf,
        )
      }
    }
    return { symbols: syms, tfPairs: pairs, matrix: mat }
  }, [signals])

  if (symbols.length === 0 || tfPairs.length === 0) return null

  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700/60 p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-slate-300">Timeframe Confluence Matrix</h3>
          <span className="text-xs text-slate-600 bg-slate-700/50 px-2 py-0.5 rounded-full">
            {signals.length} signal{signals.length !== 1 ? 's' : ''}
          </span>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-slate-500">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-sm bg-emerald-500/50 inline-block border border-emerald-500/40" />
            Long
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-sm bg-rose-500/50 inline-block border border-rose-500/40" />
            Short
          </span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="text-xs w-full">
          <thead>
            <tr>
              <th className="text-left py-2 pr-6 text-slate-500 font-medium">Symbol</th>
              {tfPairs.map(pair => {
                const [htf, ltf] = pair.split('/')
                return (
                  <th key={pair} className="text-center py-2 px-2 min-w-[90px]">
                    <div className="text-slate-400 font-semibold">{htf}</div>
                    <div className="text-slate-600">/ {ltf}</div>
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {symbols.map(sym => (
              <tr key={sym} className="border-t border-slate-700/30">
                <td className="py-2 pr-6 whitespace-nowrap">
                  <span className="font-price font-semibold text-slate-200">
                    {sym.replace('/USDT', '')}
                  </span>
                  <span className="text-slate-600">/USDT</span>
                </td>
                {tfPairs.map(pair => {
                  const signal = matrix[sym]?.[pair]
                  if (!signal) {
                    return (
                      <td key={pair} className="py-2 px-2 text-center">
                        <span className="text-slate-700">·</span>
                      </td>
                    )
                  }
                  const isLong = signal.direction === 'long'
                  return (
                    <td key={pair} className="py-2 px-2">
                      <div
                        className={`rounded-lg px-2 py-1.5 text-center border ${
                          isLong
                            ? 'bg-emerald-500/10 border-emerald-500/25'
                            : 'bg-rose-500/10 border-rose-500/25'
                        }`}
                      >
                        <div
                          className={`font-bold text-sm ${isLong ? 'text-emerald-400' : 'text-rose-400'}`}
                        >
                          {isLong ? '▲' : '▼'}
                        </div>
                        <div className={`text-[10px] tabular-nums font-price ${scoreColor(signal.score)}`}>
                          {signal.score}
                        </div>
                      </div>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
