export type Direction = 'long' | 'short'

export type SignalStatus =
  | 'active'

// Strategy confidence factors for HTF pullback continuation.
export type ConfidenceFactors = {
  htf_alignment: boolean
  pullback_active: boolean
  zone_reaction: boolean
  displacement: boolean
  micro_bos: boolean
  first_pullback: boolean
}

export type Signal = {
  id: string
  scenario_name: string
  alert_type: 'SETUP_DETECTED' | 'ENTRY_CONFIRMED'
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
