"""Tests for LiquiditySweepScenario (spec section 14)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.candle import Candle
from core.context import StructureContext
from core.models import LiquidityZone, Setup, VolumeSpike
from scenarios.liquidity_sweep import LiquiditySweepScenario


def _make_candle(open_: float, high: float, low: float, close: float, volume: float = 100.0) -> Candle:
    return Candle(
        symbol="SOL/USDT",
        timeframe="15m",
        timestamp=datetime.now(tz=timezone.utc),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        is_closed=True,
    )


def _htf_bullish() -> StructureContext:
    ctx = StructureContext(symbol="SOL/USDT", timeframe="1h")
    ctx.structure_labels = ["HH", "HL", "HH", "HL"]
    return ctx


def _htf_bearish() -> StructureContext:
    ctx = StructureContext(symbol="SOL/USDT", timeframe="1h")
    ctx.structure_labels = ["LL", "LH", "LL", "LH"]
    return ctx


scenario = LiquiditySweepScenario()


def _ltf_with_low_zone() -> StructureContext:
    ltf = StructureContext(symbol="SOL/USDT", timeframe="15m")
    ltf.liquidity_zones.append(LiquidityZone(price=130.0, kind="low", swept=False))
    for _ in range(15):
        ltf.candles.append(_make_candle(132.0, 133.0, 131.0, 132.5))
    return ltf


def test_sweep_trend_direction_only():
    """HTF bullish → sadece equal LOW (kind='low') zone için setup."""
    htf = _htf_bullish()
    # HTF bullish context'te high zone var, low zone yok
    ltf = StructureContext(symbol="SOL/USDT", timeframe="15m")
    ltf.liquidity_zones.append(LiquidityZone(price=135.0, kind="high", swept=False))
    for _ in range(15):
        ltf.candles.append(_make_candle(132.0, 133.0, 131.0, 132.5))

    setup = scenario.detect_setup(htf, ltf)
    assert setup is None  # HTF bullish wants 'low' zone, only 'high' available


def test_setup_bullish_htf_low_zone():
    """HTF bullish + unswept low zone → long setup."""
    htf = _htf_bullish()
    ltf = _ltf_with_low_zone()

    setup = scenario.detect_setup(htf, ltf)
    assert setup is not None
    assert setup.direction == "long"
    assert setup.meta.get("zone_level") == 130.0
    assert setup.meta.get("zone_kind") == "low"


def test_no_close_confirm():
    """Sweep olmadan sadece zone içi kapanış → trigger yok."""
    setup = Setup(
        scenario_name="liquidity_sweep",
        alert_type="LIQUIDITY_SWEEP",
        symbol="SOL/USDT",
        timeframe="15m",
        direction="long",
        entry_zone_low=129.5,
        entry_zone_high=130.2,
        swing_low=128.0,
        swing_high=133.0,
        invalidation_level=128.5,
        meta={"zone_level": 130.0, "zone_kind": "low"},
    )
    ltf = StructureContext(symbol="SOL/USDT", timeframe="15m")
    # Candle low is ABOVE zone_level (130.0) — no sweep occurred
    ltf.candles.append(_make_candle(130.1, 130.3, 130.05, 130.2))

    trigger = scenario.detect_trigger(setup, ltf)
    assert trigger is None


def test_sweep_triggers():
    """Candle wicks below zone.level, close above → sweep_reversal trigger."""
    setup = Setup(
        scenario_name="liquidity_sweep",
        alert_type="LIQUIDITY_SWEEP",
        symbol="SOL/USDT",
        timeframe="15m",
        direction="long",
        entry_zone_low=129.5,
        entry_zone_high=130.2,
        swing_low=128.0,
        swing_high=133.0,
        invalidation_level=128.5,
        meta={"zone_level": 130.0, "zone_kind": "low"},
    )
    ltf = StructureContext(symbol="SOL/USDT", timeframe="15m")
    # Low below zone level, close above → sweep
    ltf.candles.append(_make_candle(130.5, 131.0, 129.5, 130.8))

    trigger = scenario.detect_trigger(setup, ltf)
    assert trigger is not None
    assert trigger.conditions.sweep_reversal is True


def test_sweep_volume_spike():
    """Sweep mumunda spike → volume_confirmation TRUE."""
    now = datetime.now(tz=timezone.utc)
    setup = Setup(
        scenario_name="liquidity_sweep",
        alert_type="LIQUIDITY_SWEEP",
        symbol="SOL/USDT",
        timeframe="15m",
        direction="long",
        entry_zone_low=129.5,
        entry_zone_high=130.2,
        swing_low=128.0,
        swing_high=133.0,
        invalidation_level=128.5,
        meta={"zone_level": 130.0, "zone_kind": "low"},
    )
    ltf = StructureContext(symbol="SOL/USDT", timeframe="15m")
    c = _make_candle(130.5, 131.0, 129.5, 130.8)
    c = c.model_copy(update={"timestamp": now})
    ltf.candles.append(c)
    # Volume spike on this candle
    ltf.volume_spikes.append(VolumeSpike(volume=500.0, avg_volume=100.0, ratio=5.0, timestamp=now))

    trigger = scenario.detect_trigger(setup, ltf)
    assert trigger is not None
    assert trigger.confidence_factors.get("volume_confirmation") is True
