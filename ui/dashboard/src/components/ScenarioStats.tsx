import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  LabelList,
} from 'recharts'
import type { Stats } from '../types/signal'
import { formatScore } from '../utils/formatters'

interface Props {
  stats: Stats | null
}

const SCENARIO_COLORS: Record<string, string> = {
  htf_pullback_continuation: '#2563eb',
}

const SCENARIO_LABELS: Record<string, string> = {
  htf_pullback_continuation: 'HTF Pullback',
}

function getColor(name: string): string {
  return SCENARIO_COLORS[name] ?? '#64748b'
}

function getLabel(name: string): string {
  return SCENARIO_LABELS[name] ?? name
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2.5 text-xs shadow-xl">
      <div className="font-semibold text-slate-200 mb-2">{d.fullName}</div>
      <div className="flex justify-between gap-4">
        <span className="text-slate-500">Count</span>
        <span className="text-slate-200 font-price">{d.count}</span>
      </div>
      <div className="flex justify-between gap-4 mt-0.5">
        <span className="text-slate-500">Avg Score</span>
        <span className="text-slate-200 font-price">{formatScore(d.avg_score)}</span>
      </div>
    </div>
  )
}

export function ScenarioStats({ stats }: Props) {
  if (!stats) {
    return (
      <div className="bg-slate-800 rounded-xl border border-slate-700/60 p-4 h-64 flex items-center justify-center">
        <span className="text-slate-600 text-sm">No scenario data</span>
      </div>
    )
  }

  const data = Object.entries(stats.scenarios).map(([name, s]) => ({
    name: getLabel(name),
    fullName: name,
    count: s.count,
    avg_score: s.avg_score,
  }))

  if (data.length === 0) {
    return (
      <div className="bg-slate-800 rounded-xl border border-slate-700/60 p-4 h-64 flex items-center justify-center">
        <span className="text-slate-600 text-sm">No scenario data</span>
      </div>
    )
  }

  const total = data.reduce((s, d) => s + d.count, 0)

  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700/60 p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-300">Scenario Distribution</h3>
        <span className="text-xs text-slate-600 font-price">{total} total</span>
      </div>

      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} margin={{ top: 16, right: 4, bottom: 4, left: -20 }}>
          <XAxis
            dataKey="name"
            tick={{ fill: '#64748b', fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            interval={0}
          />
          <YAxis
            tick={{ fill: '#64748b', fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            allowDecimals={false}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
          <Bar dataKey="count" radius={[4, 4, 0, 0]}>
            <LabelList
              dataKey="count"
              position="top"
              style={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'monospace' }}
            />
            {data.map(entry => (
              <Cell key={entry.fullName} fill={getColor(entry.fullName)} fillOpacity={0.85} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Legend */}
      <div className="mt-3 space-y-1.5 border-t border-slate-700/40 pt-3">
        {data.map(d => (
          <div key={d.fullName} className="flex items-center gap-2 text-xs">
            <span
              className="w-2 h-2 rounded-sm flex-shrink-0"
              style={{ background: getColor(d.fullName) }}
            />
            <span className="text-slate-400 flex-1 truncate">{d.fullName}</span>
            <span className="text-slate-600 font-price tabular-nums">{d.count}×</span>
            <span className="text-slate-600 font-price tabular-nums w-14 text-right">
              avg <span className="text-slate-400">{formatScore(d.avg_score)}</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
