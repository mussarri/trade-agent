from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

from core.candle import Candle
from core.context import StructureContext
from core.models import FairValueGap, SwingPoint
from scenarios.htf_pullback_continuation import HtfPullbackContinuationScenario


def _c(ts: datetime, o: float, h: float, l: float, c: float) -> Candle:
    return Candle(
        symbol="ETH/USDT",
        timeframe="5m",
        timestamp=ts,
        open=o,
        high=h,
        low=l,
        close=c,
        volume=100.0,
        is_closed=True,
    )


def _htf_ctx() -> StructureContext:
    ctx = StructureContext(symbol="ETH/USDT", timeframe="1h")
    now = datetime.now(tz=timezone.utc)
    for i in range(30):
        px = 100 + i * 0.2
        ctx.candles.append(
            Candle(
                symbol="ETH/USDT",
                timeframe="1h",
                timestamp=now + timedelta(hours=i),
                open=px - 0.1,
                high=px + 0.4,
                low=px - 0.4,
                close=px,
                volume=1000.0,
                is_closed=True,
            )
        )
    ctx.external_structure_labels = ["HH", "HL", "HH", "HL", "HH"]
    return ctx


def _ltf_ctx_for_setup(prior_touch: bool = False) -> StructureContext:
    ctx = StructureContext(symbol="ETH/USDT", timeframe="5m")
    base = datetime.now(tz=timezone.utc)
    candles = [
        _c(base + timedelta(minutes=5 * 0), 100.0, 100.3, 99.8, 100.1),
        _c(base + timedelta(minutes=5 * 1), 100.1, 100.4, 99.9, 100.2),
        _c(base + timedelta(minutes=5 * 2), 100.2, 100.5, 100.0, 100.3),
        _c(base + timedelta(minutes=5 * 3), 100.3, 100.6, 100.1, 100.4),
        _c(base + timedelta(minutes=5 * 4), 100.4, 100.7, 100.2, 100.5),
        _c(base + timedelta(minutes=5 * 5), 100.5, 100.8, 100.3, 100.6),
        _c(base + timedelta(minutes=5 * 6), 100.6, 100.9, 100.4, 100.7),
        _c(base + timedelta(minutes=5 * 7), 100.7, 101.0, 100.5, 100.8),
        _c(base + timedelta(minutes=5 * 8), 100.8, 107.0, 99.5, 106.6),   # displacement up
        _c(base + timedelta(minutes=5 * 9), 106.6, 106.8, 104.0, 104.6),
        _c(base + timedelta(minutes=5 * 10), 104.6, 104.8, 103.1, 103.3),
    ]
    if prior_touch:
        candles.append(_c(base + timedelta(minutes=5 * 11), 103.3, 103.4, 102.2, 102.4))
    candles.append(_c(base + timedelta(minutes=5 * 12), 102.4, 102.7, 101.9, 102.2))
    ctx.candles.extend(candles)
    ctx.structure_labels = ["HH", "HL", "LL", "LH", "LL"]
    ctx.fvgs.append(FairValueGap(direction="long", low=101.8, high=102.6, midpoint=102.2, active=True))
    ctx.swing_highs.append(SwingPoint(index=10, price=103.2, kind="high"))
    ctx.swing_lows.append(SwingPoint(index=11, price=102.0, kind="low"))
    return ctx


def test_detect_setup_and_entry_confirmation():
    scenario = HtfPullbackContinuationScenario()
    htf = _htf_ctx()
    ltf_setup = _ltf_ctx_for_setup()
    setup = scenario.detect_setup(htf, ltf_setup)
    assert setup is not None
    assert setup.alert_type == "SETUP_DETECTED"
    assert setup.meta["state"] == "NEW"
    assert setup.meta["trend"] == "bullish"

    ltf_trigger = deepcopy(ltf_setup)
    ltf_trigger.candles.append(
        _c(datetime.now(tz=timezone.utc), 102.2, 105.0, 102.1, 104.4)
    )
    ltf_trigger.structure_labels = ["LH", "LL", "HL"]
    trigger = scenario.detect_trigger(setup, ltf_trigger)
    assert trigger is not None
    assert setup.alert_type == "ENTRY_CONFIRMED"


def test_first_pullback_rule_blocks_second_touch():
    scenario = HtfPullbackContinuationScenario()
    htf = _htf_ctx()
    ltf = _ltf_ctx_for_setup(prior_touch=True)
    assert scenario.detect_setup(htf, ltf) is None

