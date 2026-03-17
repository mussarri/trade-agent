from __future__ import annotations

from datetime import datetime, timezone

from core.models import Setup, Trigger, TriggerCondition
from risk.planner import RiskPlanner


def _trigger() -> Trigger:
    setup = Setup(
        scenario_name="htf_pullback_continuation",
        alert_type="ENTRY_CONFIRMED",
        symbol="BTC/USDT",
        timeframe="15m",
        direction="long",
        entry_zone_low=100.0,
        entry_zone_high=102.0,
        swing_low=98.0,
        swing_high=106.0,
        invalidation_level=97.0,
        meta={},
    )
    return Trigger(
        setup=setup,
        conditions=TriggerCondition(close_confirm=True),
        confidence_factors={},
        timestamp=datetime.now(tz=timezone.utc),
    )


def test_fallback_rr_is_consistent_with_default_min_rr():
    planner = RiskPlanner()
    plan = planner.plan_from_trigger(_trigger(), atr=1.0)
    assert plan.rr_ratio >= 2.0


def test_liquidity_targets_are_preferred_when_available():
    planner = RiskPlanner()
    plan = planner.plan_from_trigger(
        _trigger(),
        atr=1.0,
        swing_highs=[103.5, 104.5, 108.0],
        swing_lows=[96.0, 95.0],
    )
    assert plan.tp1 == 103.5
    assert plan.tp2 == 104.5
