from __future__ import annotations

import pytest
from datetime import datetime, timezone

from core.candle import Candle
from core.context import StructureContext
from core.ict_tracker import ICTPatternTracker
from core.models import LiquidityZone
from core.structure import FairValueGap


def _make_candle(close: float, volume: float = 100.0) -> Candle:
    return Candle(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime.now(tz=timezone.utc),
        open=close * 0.999,
        high=close * 1.005,
        low=close * 0.995,
        close=close,
        volume=volume,
        is_closed=True,
    )


def _make_ctx_with_full_ict() -> StructureContext:
    ctx = StructureContext(symbol="BTC/USDT", timeframe="15m")
    # Step 1: liquidity zone
    zone = LiquidityZone(price=49800.0, kind="low", swept=True)
    ctx.liquidity_zones.append(zone)
    # Step 2: sweep done (zone.swept=True above)
    # Step 3: displacement via BOS
    from core.context import BosEvent
    ctx.bos_events.append(BosEvent(direction="bullish", level=50000.0, timestamp=datetime.now(tz=timezone.utc)))
    # Step 4: FVG formed
    ctx.fvgs.append(FairValueGap(direction="long", low=50050.0, high=50150.0, midpoint=50100.0, active=True))
    # Step 5: price in FVG
    ctx.candles.append(_make_candle(50100.0))
    return ctx


class TestICTPatternTracker:
    def test_empty_state_is_not_full_setup(self):
        tracker = ICTPatternTracker()
        ctx = StructureContext(symbol="BTC/USDT", timeframe="15m")
        ctx.candles.append(_make_candle(50000.0))
        tracker.update("BTC/USDT", ctx)
        assert not tracker.is_full_setup("BTC/USDT")

    def test_full_ict_setup_detected(self):
        tracker = ICTPatternTracker()
        ctx = _make_ctx_with_full_ict()
        tracker.update("BTC/USDT", ctx)
        assert tracker.is_full_setup("BTC/USDT")

    def test_reset_clears_state(self):
        tracker = ICTPatternTracker()
        ctx = _make_ctx_with_full_ict()
        tracker.update("BTC/USDT", ctx)
        assert tracker.is_full_setup("BTC/USDT")
        tracker.reset("BTC/USDT")
        assert not tracker.is_full_setup("BTC/USDT")
