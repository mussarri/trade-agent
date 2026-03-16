"""Tests for FvgRetraceScenario (spec section 14)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.candle import Candle
from core.context import StructureContext
from core.models import LiquidityZone, Setup, VolumeSpike
from scenarios.fvg_retrace import FvgRetraceScenario


def _make_candle(open_: float, high: float, low: float, close: float, volume: float = 100.0) -> Candle:
    return Candle(
        symbol="ETH/USDT",
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
    ctx = StructureContext(symbol="ETH/USDT", timeframe="1h")
    ctx.structure_labels = ["HH", "HL", "HH", "HL"]
    return ctx


def _htf_bearish() -> StructureContext:
    ctx = StructureContext(symbol="ETH/USDT", timeframe="1h")
    ctx.structure_labels = ["LL", "LH", "LL", "LH"]
    return ctx


scenario = FvgRetraceScenario()


def test_weak_fvg_no_setup():
    """Displacement yok, volume spike yok → setup oluşmamalı."""
    htf = _htf_bullish()
    ltf = StructureContext(symbol="ETH/USDT", timeframe="15m")
    # Add a long FVG but no displacement or volume spike
    from core.structure import FairValueGap
    ltf.fvgs.append(FairValueGap(direction="long", low=1890.0, high=1910.0, midpoint=1900.0, active=True))
    # No volume spikes, no displacement candles
    for _ in range(5):
        ltf.candles.append(_make_candle(1900.0, 1910.0, 1890.0, 1905.0, 50.0))

    setup = scenario.detect_setup(htf, ltf)
    assert setup is None


def test_wrong_direction_fvg_skipped():
    """HTF bullish iken short FVG → setup oluşmamalı."""
    htf = _htf_bullish()
    ltf = StructureContext(symbol="ETH/USDT", timeframe="15m")
    from core.structure import FairValueGap
    ltf.fvgs.append(FairValueGap(direction="short", low=1890.0, high=1910.0, midpoint=1900.0, active=True))
    # Add volume spike to pass other checks
    ltf.volume_spikes.append(VolumeSpike(volume=500.0, avg_volume=100.0, ratio=5.0,
                                          timestamp=datetime.now(tz=timezone.utc)))
    for _ in range(5):
        ltf.candles.append(_make_candle(1900.0, 1910.0, 1890.0, 1905.0, 100.0))

    setup = scenario.detect_setup(htf, ltf)
    assert setup is None


def test_ict_full_setup_bonus():
    """Swept zone + displacement + FVG → ict_bonus = True → score +15."""
    from core.models import Trigger, TriggerCondition
    from core.structure import FairValueGap

    setup = Setup(
        scenario_name="fvg_retrace",
        alert_type="SMART_MONEY_ENTRY",
        symbol="ETH/USDT",
        timeframe="15m",
        direction="long",
        entry_zone_low=1890.0,
        entry_zone_high=1910.0,
        swing_low=1880.0,
        swing_high=1920.0,
        invalidation_level=1885.0,
        meta={"fvg_midpoint": 1900.0, "has_displacement": True},
    )

    ltf = StructureContext(symbol="ETH/USDT", timeframe="15m")
    # Swept zone exists
    ltf.liquidity_zones.append(LiquidityZone(price=1880.0, kind="low", swept=True))
    # Volume spike
    ltf.volume_spikes.append(VolumeSpike(volume=500.0, avg_volume=100.0, ratio=5.0,
                                          timestamp=datetime.now(tz=timezone.utc)))
    # Candle retracing into FVG
    ltf.candles.append(_make_candle(1895.0, 1912.0, 1888.0, 1895.0))

    trigger = scenario.detect_trigger(setup, ltf)
    assert trigger is not None
    assert trigger.setup.meta.get("ict_bonus") is True

    from scoring.scorer import score as compute_score, ICT_FULL_SETUP_BONUS
    s = compute_score(trigger)
    # htf_alignment(30) + fvg_or_ob_presence(25) + volume_confirmation(20) + ICT(15) = at least 90
    assert s >= 90
