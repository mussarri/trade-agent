from __future__ import annotations

from datetime import datetime, timezone

from core.context import BosEvent, StructureContext
from core.models import Setup
from core.structure import FairValueGap
from scenarios.bos_continuation import BosContinuationScenario


def _htf_bullish() -> StructureContext:
    ctx = StructureContext(symbol="BTC/USDT", timeframe="1h")
    ctx.external_structure_labels = ["HH", "HL", "HH", "HL"]
    return ctx


def _htf_neutral() -> StructureContext:
    return StructureContext(symbol="BTC/USDT", timeframe="1h")


def _ltf_with_external_bos(displacement: bool = True) -> StructureContext:
    ltf = StructureContext(symbol="BTC/USDT", timeframe="15m")
    ltf.bos_events.append(
        BosEvent(
            direction="bullish",
            level=50000.0,
            timestamp=datetime.now(tz=timezone.utc),
            structure_kind="external",
            displacement=displacement,
        )
    )
    ltf.swing_lows.append(type("SP", (), {"price": 49500.0})())
    ltf.swing_highs.append(type("SP", (), {"price": 50500.0})())
    ltf.fvgs.append(FairValueGap(direction="long", low=49700.0, high=50000.0, midpoint=49850.0, active=True))
    ltf.candles.append(type("C", (), {"close": 49990.0})())
    return ltf


def test_requires_external_bos_with_displacement():
    scenario = BosContinuationScenario()
    setup = scenario.detect_setup(_htf_bullish(), _ltf_with_external_bos(displacement=False))
    assert setup is None


def test_rejects_neutral_htf():
    scenario = BosContinuationScenario()
    setup = scenario.detect_setup(_htf_neutral(), _ltf_with_external_bos(displacement=True))
    assert setup is None


def test_valid_external_continuation_setup():
    scenario = BosContinuationScenario()
    setup = scenario.detect_setup(_htf_bullish(), _ltf_with_external_bos(displacement=True))
    assert setup is not None
    assert setup.direction == "long"
    assert setup.meta.get("bos_kind") == "external"


def test_trigger_close_confirm_works():
    scenario = BosContinuationScenario()
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
        meta={"bos_level": 50200.0, "has_fvg": True, "bos_kind": "external"},
    )
    ltf = StructureContext(symbol="BTC/USDT", timeframe="15m")
    ltf.candles.append(type("C", (), {"open": 49900.0, "high": 50150.0, "low": 49850.0, "close": 50100.0, "timestamp": datetime.now(tz=timezone.utc)})())

    trigger = scenario.detect_trigger(setup, ltf)
    assert trigger is not None
    assert trigger.conditions.close_confirm is True
