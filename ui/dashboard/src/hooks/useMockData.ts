import { useMemo } from 'react'
import type { Signal, Stats } from '../types/signal'

const now = new Date()
const ago = (minutes: number) => new Date(now.getTime() - minutes * 60 * 1000).toISOString()

export const MOCK_SIGNALS: Signal[] = [
  {
    id: 'sig-001',
    scenario_name: 'bos_continuation',
    alert_type: 'BOS_CONTINUATION',
    pair: 'BTCUSDT',
    symbol: 'BTC/USDT',
    direction: 'long',
    score: 85,
    timeframe_htf: '1h',
    timeframe_ltf: '15m',
    htf_trend: 'bullish',
    session: 'london',
    ict_full_setup: false,
    scenario_detail: 'bos_continuation | long | close_confirm',
    timestamp: ago(4),
    confidence_factors: {
      htf_alignment: true,
      fvg_or_ob_presence: true,
      volume_confirmation: true,
      liquidity_confluence: false,
      session_time: true,
    },
    entry_low: 83100.0,
    entry_high: 83450.0,
    stop_loss: 82600.0,
    tp1: 84500.0,
    tp2: 85800.0,
    tp3: 87200.0,
    rr_ratio: 3.2,
    invalidation_level: 82450.0,
    status: 'active',
  },
  {
    id: 'sig-002',
    scenario_name: 'fvg_retrace',
    alert_type: 'SMART_MONEY_ENTRY',
    pair: 'ETHUSDT',
    symbol: 'ETH/USDT',
    direction: 'long',
    score: 95,
    timeframe_htf: '1h',
    timeframe_ltf: '15m',
    htf_trend: 'bullish',
    session: 'london',
    ict_full_setup: true,
    scenario_detail: 'fvg_retrace | long | sweep_reversal | ICT Full Setup',
    timestamp: ago(12),
    confidence_factors: {
      htf_alignment: true,
      fvg_or_ob_presence: true,
      volume_confirmation: true,
      liquidity_confluence: true,
      session_time: true,
    },
    entry_low: 1891.0,
    entry_high: 1902.0,
    stop_loss: 1874.0,
    tp1: 1930.0,
    tp2: 1965.0,
    tp3: 2010.0,
    rr_ratio: 2.8,
    invalidation_level: 1870.0,
    status: 'active',
  },
  {
    id: 'sig-003',
    scenario_name: 'liquidity_sweep',
    alert_type: 'LIQUIDITY_SWEEP',
    pair: 'SOLUSDT',
    symbol: 'SOL/USDT',
    direction: 'long',
    score: 70,
    timeframe_htf: '1h',
    timeframe_ltf: '15m',
    htf_trend: 'bullish',
    session: 'new_york',
    ict_full_setup: false,
    scenario_detail: 'liquidity_sweep | long | sweep_reversal',
    timestamp: ago(31),
    confidence_factors: {
      htf_alignment: true,
      fvg_or_ob_presence: false,
      volume_confirmation: true,
      liquidity_confluence: true,
      session_time: true,
    },
    entry_low: 128.5,
    entry_high: 130.2,
    stop_loss: 126.8,
    tp1: 133.5,
    tp2: 137.0,
    tp3: 142.0,
    rr_ratio: 2.6,
    invalidation_level: 126.5,
    status: 'tp1_hit',
  },
]

export const MOCK_STATS: Stats = {
  total_signals_today: 3,
  active_signals: 2,
  scenarios: {
    bos_continuation: { count: 1, avg_score: 85 },
    fvg_retrace:      { count: 1, avg_score: 95 },
    liquidity_sweep:  { count: 1, avg_score: 70 },
  },
  symbols: {
    'BTC/USDT': { active: 1, last_structure: 'bullish' },
    'ETH/USDT': { active: 1, last_structure: 'bullish' },
    'SOL/USDT': { active: 0, last_structure: 'bullish' },
  },
}

export function useMockData() {
  const signals = useMemo(() => MOCK_SIGNALS, [])
  const stats = useMemo(() => MOCK_STATS, [])
  return { signals, stats }
}
