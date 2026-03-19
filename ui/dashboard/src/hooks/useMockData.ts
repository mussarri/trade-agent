import { useMemo } from 'react'
import type { Signal, Stats } from '../types/signal'

const now = new Date()
const ago = (minutes: number) => new Date(now.getTime() - minutes * 60 * 1000).toISOString()

const BASE_FACTORS = {
  htf_alignment: true,
  pullback_active: true,
  zone_reaction: true,
  displacement: true,
  micro_bos: true,
  first_pullback: true,
}

export const MOCK_SIGNALS: Signal[] = [
  {
    id: 'sig-setup-001',
    scenario_name: 'htf_pullback_continuation',
    alert_type: 'SETUP_DETECTED',
    pair: 'ETHUSDT',
    symbol: 'ETH/USDT',
    direction: 'long',
    score: 55,
    timeframe_htf: '1h',
    timeframe_ltf: '5m',
    htf_trend: 'bullish',
    session: 'london',
    ict_full_setup: false,
    scenario_detail: 'htf_pullback_continuation | long | setup',
    timestamp: ago(12),
    confidence_factors: BASE_FACTORS,
    entry_low: 2176.0,
    entry_high: 2180.0,
    stop_loss: 2168.0,
    tp1: 0,
    tp2: 0,
    tp3: 0,
    rr_ratio: 0,
    invalidation_level: 2168.0,
    status: 'active',
  },
  {
    id: 'sig-entry-001',
    scenario_name: 'htf_pullback_continuation',
    alert_type: 'ENTRY_CONFIRMED',
    pair: 'ETHUSDT',
    symbol: 'ETH/USDT',
    direction: 'long',
    score: 100,
    timeframe_htf: '1h',
    timeframe_ltf: '5m',
    htf_trend: 'bullish',
    session: 'london',
    ict_full_setup: false,
    scenario_detail: 'htf_pullback_continuation | long | confirmed',
    timestamp: ago(8),
    confidence_factors: BASE_FACTORS,
    entry_low: 2178.2,
    entry_high: 2178.2,
    stop_loss: 2168.0,
    tp1: 2200.0,
    tp2: 2215.0,
    tp3: 2230.0,
    rr_ratio: 2.1,
    invalidation_level: 2168.0,
    status: 'active',
  },
]

export const MOCK_STATS: Stats = {
  total_signals_today: 2,
  active_signals: 2,
  scenarios: {
    htf_pullback_continuation: { count: 2, avg_score: 77.5 },
  },
  symbols: {
    'ETH/USDT': { active: 2, last_structure: 'bullish' },
  },
}

export function useMockData() {
  const signals = useMemo(() => MOCK_SIGNALS, [])
  const stats = useMemo(() => MOCK_STATS, [])
  return { signals, stats }
}
