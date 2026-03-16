export type Direction = 'long' | 'short'

export type SignalStatus =
  | 'active'
  | 'tp1_hit'
  | 'tp2_hit'
  | 'tp3_hit'
  | 'stopped'
  | 'invalidated'
  | 'expired'

// v2.0 — 5 factors (clean_market_structure kaldırıldı)
export type ConfidenceFactors = {
  htf_alignment: boolean
  fvg_or_ob_presence: boolean
  volume_confirmation: boolean
  liquidity_confluence: boolean
  session_time: boolean
}

export type Signal = {
  id: string
  scenario_name: string
  alert_type: string        // "BOS_CONTINUATION" | "SMART_MONEY_ENTRY" | "LIQUIDITY_SWEEP"
  pair: string              // "BTCUSDT" format
  symbol: string
  direction: Direction
  score: number
  timeframe_htf: string
  timeframe_ltf: string
  htf_trend: string         // "bullish" | "bearish"
  session: string           // "london" | "new_york" | "overlap" | "asian" | "off"
  ict_full_setup: boolean
  scenario_detail: string
  timestamp: string
  confidence_factors: ConfidenceFactors
  entry_low: number
  entry_high: number
  stop_loss: number
  tp1: number
  tp2: number
  tp3: number
  rr_ratio: number
  invalidation_level: number
  status: SignalStatus
}

export type ScenarioStats = {
  count: number
  avg_score: number
}

export type SymbolStats = {
  active: number
  last_structure: string
}

export type Stats = {
  total_signals_today: number
  active_signals: number
  scenarios: Record<string, ScenarioStats>
  symbols: Record<string, SymbolStats>
}

export type SortBy = 'score' | 'time' | 'rr'

export type FilterState = {
  symbol: string
  direction: '' | 'long' | 'short'
  scenario: string
  minScore: number
  sortBy: SortBy
}
