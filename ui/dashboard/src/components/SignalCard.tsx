import type { Signal, ConfidenceFactors } from '../types/signal'
import {
  formatPrice,
  formatRR,
  formatTimeAgo,
  scoreColor,
  scoreBarColor,
  sessionLabel,
  trendColor,
  alertTypeEmoji,
} from '../utils/formatters'

interface Props {
  signal: Signal
  isNew?: boolean
}

const CONFIDENCE_LABELS: Record<keyof ConfidenceFactors, string> = {
  htf_alignment: 'HTF Trend',
  pullback_active: 'Pullback',
  zone_reaction: 'Zone Reaction',
  displacement: 'Displacement',
  micro_bos: 'Micro BOS',
  first_pullback: 'First Pullback',
}

function PriceBar({ signal }: { signal: Signal }) {
  const { stop_loss, entry_low, entry_high, tp1, tp2, tp3 } = signal
  const prices = [stop_loss, entry_low, entry_high, tp1, tp2, tp3].filter(p => p > 0)
  if (prices.length < 2) return null

  const min = Math.min(...prices)
  const max = Math.max(...prices)
  const range = max - min
  if (range === 0) return null

  const pct = (p: number) => `${((p - min) / range) * 100}%`
  const entryLeftPct  = ((entry_low  - min) / range) * 100
  const entryRightPct = 100 - ((entry_high - min) / range) * 100
  const lastTp = tp3 || tp2 || tp1

  return (
    <div className="my-2">
      <div className="relative h-3.5 bg-slate-700/50 rounded-full mx-0.5">
        {entry_low > 0 && entry_high > 0 && (
          <div
            className="absolute inset-y-0 bg-amber-400/20 border-x border-amber-400/40"
            style={{ left: `${entryLeftPct}%`, right: `${entryRightPct}%` }}
          />
        )}
        {stop_loss > 0 && (
          <div className="absolute inset-y-[-2px] w-0.5 bg-rose-500 rounded-full" style={{ left: pct(stop_loss) }} />
        )}
        {tp1 > 0 && (
          <div className="absolute inset-y-[-1px] w-0.5 bg-emerald-400/50 rounded-full" style={{ left: pct(tp1) }} />
        )}
        {tp2 > 0 && (
          <div className="absolute inset-y-[-1px] w-0.5 bg-emerald-400/75 rounded-full" style={{ left: pct(tp2) }} />
        )}
        {tp3 > 0 && (
          <div className="absolute inset-y-[-2px] w-0.5 bg-emerald-400 rounded-full" style={{ left: pct(tp3) }} />
        )}
      </div>
      <div className="flex justify-between text-[9px] mt-1 px-0.5 text-slate-600 font-price tabular-nums">
        <span className="text-rose-500/60">{formatPrice(stop_loss)}</span>
        <span className="text-amber-400/50">entry</span>
        <span className="text-emerald-500/60">{formatPrice(lastTp)}</span>
      </div>
    </div>
  )
}

export function SignalCard({ signal, isNew = false }: Props) {
  const isLong = signal.direction === 'long'
  const factors = Object.keys(signal.confidence_factors) as Array<keyof ConfidenceFactors>
  const activeFactors = factors.filter(k => signal.confidence_factors[k]).length

  return (
    <div
      className={`
        bg-slate-800 rounded-xl border p-4 flex flex-col gap-3
        transition-all duration-200 cursor-default
        hover:shadow-xl hover:shadow-black/30
        ${isLong
          ? 'border-slate-700/60 hover:border-emerald-500/25'
          : 'border-slate-700/60 hover:border-rose-500/25'
        }
        ${isNew ? 'animate-slide-in' : ''}
      `}
    >
      {/* Row 1: Symbol + direction + ICT badge */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap min-w-0">
          <span className="font-price font-bold text-slate-100 tracking-tight whitespace-nowrap">
            {signal.symbol.replace('/USDT', '')}
            <span className="text-slate-500 font-normal text-sm">/USDT</span>
          </span>
          <span
            className={`text-[11px] font-bold px-2 py-0.5 rounded-full border flex-shrink-0 ${
              isLong
                ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                : 'bg-rose-500/15 text-rose-400 border-rose-500/30'
            }`}
          >
            {isLong ? '▲ LONG' : '▼ SHORT'}
          </span>
          {signal.ict_full_setup && (
            <span className="text-[11px] px-1.5 py-0.5 rounded-full bg-amber-400/15 text-amber-300 border border-amber-400/30 flex-shrink-0">
              ⭐ ICT
            </span>
          )}
        </div>

        {/* TF pair + alert type emoji */}
        <div className="flex-shrink-0 text-right space-y-1">
          <div className="text-lg leading-none">{alertTypeEmoji(signal.alert_type)}</div>
          <div className="text-[10px] font-price text-slate-500 bg-slate-700/50 px-2 py-0.5 rounded-full whitespace-nowrap border border-slate-600/30">
            {signal.timeframe_htf} → {signal.timeframe_ltf}
          </div>
        </div>
      </div>

      {/* Row 2: Alert type + time */}
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-slate-400 bg-slate-700/40 px-2.5 py-1 rounded-lg truncate">
          {signal.alert_type || signal.scenario_name}
        </span>
        <span className="text-[11px] text-slate-600 flex-shrink-0">{formatTimeAgo(signal.timestamp)}</span>
      </div>

      {/* Row 3: HTF trend + session */}
      {(signal.htf_trend || signal.session) && (
        <div className="flex items-center gap-2 text-[11px]">
          {signal.htf_trend && (
            <span className={`flex items-center gap-1 ${trendColor(signal.htf_trend)}`}>
              <span>{signal.htf_trend === 'bullish' ? '▲' : '▼'}</span>
              <span className="capitalize">{signal.htf_trend}</span>
            </span>
          )}
          {signal.htf_trend && signal.session && (
            <span className="text-slate-700">·</span>
          )}
          {signal.session && (
            <span className="text-slate-500">{sessionLabel(signal.session)}</span>
          )}
        </div>
      )}

      {/* Row 4: Score + bar + R:R */}
      <div className="flex items-center gap-3">
        <div className="flex-shrink-0 text-center w-11">
          <div className={`text-2xl font-bold font-price tabular-nums leading-none ${scoreColor(signal.score)}`}>
            {signal.score}
          </div>
          <div className="text-[9px] text-slate-600 mt-0.5">score</div>
        </div>

        <div className="flex-1 min-w-0">
          <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${scoreBarColor(signal.score)}`}
              style={{ width: `${signal.score}%` }}
            />
          </div>
          {/* Confidence dots */}
          <div className="flex items-center gap-1 mt-1.5">
            {factors.map(key => (
              <div
                key={key}
                title={CONFIDENCE_LABELS[key]}
                className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                  signal.confidence_factors[key] ? 'bg-emerald-400' : 'bg-slate-700'
                }`}
              />
            ))}
            <span className="text-[10px] text-slate-600 ml-0.5 font-price">
              {activeFactors}/{factors.length}
            </span>
          </div>
        </div>

        <div className="flex-shrink-0 text-right">
          <div className="font-price text-lg font-bold text-violet-400 leading-none">
            {formatRR(signal.rr_ratio)}
          </div>
          <div className="text-[9px] text-slate-600 mt-0.5">R:R</div>
        </div>
      </div>

      {/* Price level visualizer */}
      <PriceBar signal={signal} />

      {/* Price levels grid */}
      <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
        <div className="flex justify-between items-center">
          <span className="text-slate-500">Entry Low</span>
          <span className="font-price text-slate-300 tabular-nums">{formatPrice(signal.entry_low)}</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-rose-400/70">Stop Loss</span>
          <span className="font-price text-rose-400 tabular-nums">{formatPrice(signal.stop_loss)}</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-emerald-400/50">TP1</span>
          <span className="font-price text-emerald-400/60 tabular-nums">{formatPrice(signal.tp1)}</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-emerald-400/70">TP2</span>
          <span className="font-price text-emerald-400/75 tabular-nums">{formatPrice(signal.tp2)}</span>
        </div>
        <div className="flex justify-between items-center col-span-2 pt-1 border-t border-slate-700/30 mt-0.5">
          <span className="text-emerald-400">TP3</span>
          <span className="font-price text-emerald-400 tabular-nums font-semibold">
            {formatPrice(signal.tp3)}
          </span>
        </div>
      </div>

      {/* Confidence factor tags */}
      <div className="flex flex-wrap gap-1">
        {factors.map(key => {
          const active = signal.confidence_factors[key]
          return (
            <span
              key={key}
              className={`text-[10px] px-1.5 py-0.5 rounded border ${
                active
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                  : 'bg-slate-700/20 text-slate-600 border-slate-700/30'
              }`}
            >
              {active ? '✓' : '✗'} {CONFIDENCE_LABELS[key]}
            </span>
          )
        })}
      </div>

      {/* Scenario detail */}
      {signal.scenario_detail && (
        <div className="text-[10px] text-slate-600 bg-slate-700/20 rounded-lg px-2.5 py-1.5 font-price truncate">
          📝 {signal.scenario_detail}
        </div>
      )}

      {/* Invalidation */}
      {signal.invalidation_level > 0 && (
        <div className="flex items-center gap-2 text-[11px] text-amber-500/70 bg-amber-500/5 border border-amber-500/15 rounded-lg px-2.5 py-1.5">
          <svg className="w-3 h-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
          </svg>
          <span>
            Invalidation:{' '}
            <span className="font-price tabular-nums text-amber-400/90">
              {formatPrice(signal.invalidation_level)}
            </span>
          </span>
        </div>
      )}
    </div>
  )
}
