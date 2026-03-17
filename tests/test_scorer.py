"""Tests for the v2.0 confidence scorer."""
from datetime import datetime, timezone

from core.models import Setup, Trigger, TriggerCondition
from scoring.scorer import ICT_FULL_SETUP_BONUS, MIN_RR_RATIO, MIN_SCORE, score


def _make_trigger(factors: dict[str, bool], ict_bonus: bool = False) -> Trigger:
    setup = Setup(
        scenario_name="htf_pullback_continuation",
        alert_type="ENTRY_CONFIRMED",
        symbol="BTC/USDT",
        timeframe="15m",
        direction="long",
        entry_zone_low=49800.0,
        entry_zone_high=50000.0,
        swing_low=49000.0,
        swing_high=51000.0,
        invalidation_level=49000.0,
        meta={"ict_bonus": ict_bonus},
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
    """All strategy factors true -> 100."""
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
    """Only HTF alignment -> 20."""
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
    """htf_alignment(20) + pullback_active(15) = 35."""
    t = _make_trigger({
        "htf_alignment": True,
        "pullback_active": True,
        "zone_reaction": False,
        "displacement": False,
        "micro_bos": False,
        "first_pullback": False,
    })
    assert score(t) == 35


def test_score_ict_bonus_via_meta():
    """ICT bonus meta'dan alınıyor → +15, capped at 100."""
    t = _make_trigger({
        "htf_alignment": True,
        "pullback_active": True,
        "zone_reaction": True,
        "displacement": True,
        "micro_bos": True,
        "first_pullback": True,
    }, ict_bonus=True)
    # 100 + 15 → capped at 100
    assert score(t) == 100


def test_score_ict_bonus_via_param():
    """ICT bonus parametre ile de çalışıyor."""
    t = _make_trigger({
        "htf_alignment": True,
        "pullback_active": True,
        "zone_reaction": False,
        "displacement": False,
        "micro_bos": False,
        "first_pullback": False,
    })
    # 20 + 15 + 15 = 50
    assert score(t, ict_bonus=ICT_FULL_SETUP_BONUS) == 50


def test_score_unknown_factors_ignored():
    """Bilinmeyen faktörler yok sayılır."""
    t = _make_trigger({
        "htf_alignment": True,
        "unknown_factor": True,
        "another_unknown": True,
    })
    assert score(t) == 20
