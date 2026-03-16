"""Tests for BosContinuationScenario (spec section 14)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.candle import Candle
from core.context import StructureContext
from core.models import Setup
from scenarios.bos_continuation import BosContinuationScenario


def _make_candle(open_: float, high: float, low: float, close: float, volume: float = 100.0) -> Candle:
    return Candle(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime.now(tz=timezone.utc),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        is_closed=True,
    )


def _make_context(symbol: str = "BTC/USDT", tf: str = "15m") -> StructureContext:
    return StructureContext(symbol=symbol, timeframe=tf)


def _htf_bullish() -> StructureContext:
    ctx = _make_context(tf="1h")
    # Force bullish structure_labels
    ctx.structure_labels = ["HH", "HL", "HH", "HL"]
    return ctx


def _htf_bearish() -> StructureContext:
    ctx = _make_context(tf="1h")
    ctx.structure_labels = ["LL", "LH", "LL", "LH"]
    return ctx


def _htf_neutral() -> StructureContext:
    ctx = _make_context(tf="1h")
    return ctx


scenario = BosContinuationScenario()


def test_long_setup_bullish_htf():
    """HTF bullish + LTF BOS bullish → long setup oluşmalı."""
    htf = _htf_bullish()
    ltf = _make_context()
    # Add a bullish BOS event
    from core.context import BosEvent
    ltf.bos_events.append(BosEvent(direction="bullish", level=50000.0, timestamp=datetime.now(tz=timezone.utc)))
    ltf.swing_lows.append(type("SP", (), {"price": 49500.0})())
    ltf.swing_highs.append(type("SP", (), {"price": 50500.0})())

    setup = scenario.detect_setup(htf, ltf)
    assert setup is not None
    assert setup.direction == "long"
    assert setup.meta.get("bos_level") == 50000.0


def test_no_setup_neutral_htf():
    """HTF neutral → setup oluşmamalı."""
    htf = _htf_neutral()
    ltf = _make_context()
    from core.context import BosEvent
    ltf.bos_events.append(BosEvent(direction="bullish", level=50000.0, timestamp=datetime.now(tz=timezone.utc)))

    setup = scenario.detect_setup(htf, ltf)
    assert setup is None


def test_no_long_setup_bearish_htf():
    """HTF bearish → long setup oluşmamalı (BOS direction mismatch)."""
    htf = _htf_bearish()
    ltf = _make_context()
    from core.context import BosEvent
    # LTF has bullish BOS but HTF is bearish → mismatch
    ltf.bos_events.append(BosEvent(direction="bullish", level=50000.0, timestamp=datetime.now(tz=timezone.utc)))

    setup = scenario.detect_setup(htf, ltf)
    assert setup is None


def test_trigger_close_confirm():
    """Bölge içi üst yarı kapanış → trigger."""
    setup = Setup(
        scenario_name="bos_continuation",
        alert_type="BOS_CONTINUATION",
        symbol="BTC/USDT",
        timeframe="15m",
        direction="long",
        entry_zone_low=49800.0,
        entry_zone_high=50200.0,
        swing_low=49500.0,
        swing_high=50500.0,
        invalidation_level=49750.0,
        meta={"bos_level": 50200.0, "has_fvg": False},
    )
    ltf = _make_context()
    # Close inside zone, above midpoint (50000)
    ltf.candles.append(_make_candle(49900.0, 50150.0, 49850.0, 50100.0))

    trigger = scenario.detect_trigger(setup, ltf)
    assert trigger is not None
    assert trigger.conditions.close_confirm is True
    assert trigger.conditions.sweep_reversal is False


def test_trigger_sweep_reversal():
    """Wick dışı + geri kapanış → trigger."""
    setup = Setup(
        scenario_name="bos_continuation",
        alert_type="BOS_CONTINUATION",
        symbol="BTC/USDT",
        timeframe="15m",
        direction="long",
        entry_zone_low=49800.0,
        entry_zone_high=50200.0,
        swing_low=49500.0,
        swing_high=50500.0,
        invalidation_level=49750.0,
        meta={"bos_level": 50200.0, "has_fvg": False},
    )
    ltf = _make_context()
    # Low below zone_low, close above zone_low → sweep reversal
    ltf.candles.append(_make_candle(49850.0, 49950.0, 49700.0, 49900.0))

    trigger = scenario.detect_trigger(setup, ltf)
    assert trigger is not None
    assert trigger.conditions.sweep_reversal is True


def test_invalidation_level():
    """BOS seviyesi altı kapanış → setup iptal."""
    setup = Setup(
        scenario_name="bos_continuation",
        alert_type="BOS_CONTINUATION",
        symbol="BTC/USDT",
        timeframe="15m",
        direction="long",
        entry_zone_low=49800.0,
        entry_zone_high=50200.0,
        swing_low=49500.0,
        swing_high=50500.0,
        invalidation_level=49750.0,
        meta={},
    )
    ltf = _make_context()
    # Close below invalidation level
    ltf.candles.append(_make_candle(49800.0, 49820.0, 49600.0, 49700.0))

    assert scenario.is_invalidated(setup, ltf) is True


def test_invalidation_timeout():
    """20 mum → setup iptal."""
    setup = Setup(
        scenario_name="bos_continuation",
        alert_type="BOS_CONTINUATION",
        symbol="BTC/USDT",
        timeframe="15m",
        direction="long",
        entry_zone_low=49800.0,
        entry_zone_high=50200.0,
        swing_low=49500.0,
        swing_high=50500.0,
        invalidation_level=49750.0,
        max_candles=20,
        candles_elapsed=20,
        meta={},
    )
    ltf = _make_context()
    ltf.candles.append(_make_candle(50000.0, 50100.0, 49950.0, 50050.0))

    assert scenario.is_invalidated(setup, ltf) is True
