"""Tests for confidence scoring in HTF pullback continuation."""
from datetime import datetime, timezone

from core.models import Setup, Trigger, TriggerCondition
from scoring.scorer import MIN_RR_RATIO, MIN_SCORE, score


def _make_trigger(factors: dict[str, bool]) -> Trigger:
    setup = Setup(
        scenario_name="htf_pullback_continuation",
        alert_type="ENTRY_CONFIRMED",
        symbol="BTC/USDT",
        timeframe="5m",
        direction="long",
        entry_zone_low=49800.0,
        entry_zone_high=50000.0,
        swing_low=49000.0,
        swing_high=51000.0,
        invalidation_level=49000.0,
        meta={},
    )
    return Trigger(
        setup=setup,
        conditions=TriggerCondition(),
        confidence_factors=factors,
        timestamp=datetime.now(tz=timezone.utc),
    )


def test_min_score_default():
    assert MIN_SCORE == 65


def test_min_rr_default():
    assert MIN_RR_RATIO == 2.0


def test_score_all_true():
    t = _make_trigger({
        "htf_alignment": True,
        "pullback_active": True,
        "zone_reaction": True,
        "displacement": True,
        "micro_bos": True,
        "first_pullback": True,
    })
    assert score(t) == 100


def test_score_htf_only():
    t = _make_trigger({
        "htf_alignment": True,
        "pullback_active": False,
        "zone_reaction": False,
        "displacement": False,
        "micro_bos": False,
        "first_pullback": False,
    })
    assert score(t) == 20


def test_score_htf_plus_pullback():
    t = _make_trigger({
        "htf_alignment": True,
        "pullback_active": True,
        "zone_reaction": False,
        "displacement": False,
        "micro_bos": False,
        "first_pullback": False,
    })
    assert score(t) == 35


def test_score_unknown_factors_ignored():
    t = _make_trigger({
        "htf_alignment": True,
        "unknown_factor": True,
        "another_unknown": True,
    })
    assert score(t) == 20
