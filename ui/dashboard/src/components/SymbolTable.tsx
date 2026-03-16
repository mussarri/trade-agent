import type { Stats } from '../types/signal'
import { trendColor } from '../utils/formatters'

interface Props {
  stats: Stats | null
}

const SYMBOL_ICONS: Record<string, string> = {
  'BTC/USDT': '₿',
  'ETH/USDT': 'Ξ',
  'SOL/USDT': '◎',
  'BNB/USDT': '⬡',
  'AVAX/USDT': '▲',
}

export function SymbolTable({ stats }: Props) {
  if (!stats) {
    return (
      <div className="bg-slate-800 rounded-xl border border-slate-700/60 p-4 h-64 flex items-center justify-center">
        <span className="text-slate-600 text-sm">No symbol data</span>
      </div>
    )
  }

  const rows = Object.entries(stats.symbols)

  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700/60 p-4">
      <h3 className="text-sm font-semibold text-slate-300 mb-4">Symbol Overview</h3>
      <div className="overflow-hidden rounded-lg border border-slate-700/60">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-slate-700/60 bg-slate-700/30">
              <th className="text-left py-2 px-3 text-slate-500 font-medium">Symbol</th>
              <th className="text-center py-2 px-3 text-slate-500 font-medium">Active</th>
              <th className="text-left py-2 px-3 text-slate-500 font-medium">Last Structure</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([symbol, data], i) => (
              <tr
                key={symbol}
                className={`${i !== rows.length - 1 ? 'border-b border-slate-700/40' : ''} hover:bg-slate-700/20 transition-colors`}
              >
                <td className="py-2.5 px-3">
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-6 rounded-md bg-slate-700 flex items-center justify-center text-slate-400 font-mono text-xs">
                      {SYMBOL_ICONS[symbol] ?? '?'}
                    </span>
                    <span className="font-price text-slate-200 font-medium">{symbol.replace('/USDT', '')}</span>
                    <span className="text-slate-600">/USDT</span>
                  </div>
                </td>
                <td className="py-2.5 px-3 text-center">
                  {data.active > 0 ? (
                    <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 font-bold">
                      {data.active}
                    </span>
                  ) : (
                    <span className="text-slate-600">—</span>
                  )}
                </td>
                <td className="py-2.5 px-3">
                  <span className={`capitalize ${trendColor(data.last_structure)}`}>
                    {data.last_structure || '—'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
