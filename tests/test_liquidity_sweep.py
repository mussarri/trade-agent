from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.candle import Candle
from core.context import BosEvent, ChochEvent, StructureContext
from core.models import LiquiditySweepEvent, Setup
from scenarios.liquidity_sweep import LiquiditySweepScenario


def _make_candle(price: float) -> Candle:
    now = datetime.now(tz=timezone.utc)
    return Candle(
        symbol="SOL/USDT",
        timeframe="15m",
        timestamp=now,
        open=price * 0.999,
        high=price * 1.002,
        low=price * 0.998,
        close=price,
        volume=100,
        is_closed=True,
    )


def _htf(direction: str) -> StructureContext:
    ctx = StructureContext(symbol="SOL/USDT", timeframe="1h")
    if direction == "bullish":
        ctx.external_structure_labels = ["HH", "HL", "HH", "HL"]
    elif direction == "bearish":
        ctx.external_structure_labels = ["LL", "LH", "LL", "LH"]
    return ctx


def test_setup_requires_recent_sweep():
    scenario = LiquiditySweepScenario()
    ltf = StructureContext(symbol="SOL/USDT", timeframe="15m")
    for _ in range(20):
        ltf.candles.append(_make_candle(130.0))
    assert scenario.detect_setup(_htf("bullish"), ltf) is None


def test_trigger_requires_post_sweep_structure_shift():
    scenario = LiquiditySweepScenario()
    ltf = StructureContext(symbol="SOL/USDT", timeframe="15m")
    for _ in range(20):
        ltf.candles.append(_make_candle(130.0))
    sweep_ts = datetime.now(tz=timezone.utc) - timedelta(minutes=5)
    ltf.recent_sweeps.append(LiquiditySweepEvent(direction="bullish", price=130.0, timestamp=sweep_ts))
    setup = scenario.detect_setup(_htf("bullish"), ltf)
    assert setup is not None
    assert scenario.detect_trigger(setup, ltf) is None


def test_trigger_fires_after_bos_or_choch_confirmation():
    scenario = LiquiditySweepScenario()
    ltf = StructureContext(symbol="SOL/USDT", timeframe="15m")
    for _ in range(20):
        ltf.candles.append(_make_candle(130.0))
    sweep_ts = datetime.now(tz=timezone.utc) - timedelta(minutes=10)
    ltf.recent_sweeps.append(LiquiditySweepEvent(direction="bullish", price=130.0, timestamp=sweep_ts))
    setup = scenario.detect_setup(_htf("bullish"), ltf)
    assert setup is not None
    ltf.bos_events.append(
        BosEvent(
            direction="bullish",
            level=131.0,
            timestamp=datetime.now(tz=timezone.utc),
            structure_kind="external",
            displacement=True,
        )
    )
    ltf.choch_events.append(
        ChochEvent(direction="bullish", timestamp=datetime.now(tz=timezone.utc), structure_kind="external", candle_index=10)
    )
    ltf.candles.append(_make_candle(131.0))
    trigger = scenario.detect_trigger(setup, ltf)
    assert trigger is not None
    assert trigger.conditions.breakout_close is True
