"""Tests for Pipeline hard filter, cooldown, confluence (spec section 14)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from core.context import StructureContext
from core.models import AlertPayload, RiskPlan
from core.pipeline import Pipeline


def _make_alert(symbol: str, direction: str, score: int = 70) -> AlertPayload:
    now = datetime.now(tz=timezone.utc)
    return AlertPayload(
        scenario_name="bos_continuation",
        alert_type="BOS_CONTINUATION",
        symbol=symbol,
        pair=symbol.replace("/", ""),
        timeframe="15m",
        direction=direction,
        score=score,
        confidence_factors={
            "htf_alignment": True,
            "fvg_or_ob_presence": True,
            "volume_confirmation": False,
            "liquidity_confluence": False,
            "session_time": True,
        },
        risk_plan=RiskPlan(
            entry_low=50000.0,
            entry_high=50200.0,
            stop_loss=49500.0,
            tp1=51000.0,
            tp2=52000.0,
            tp3=53000.0,
            rr_ratio=2.5,
            position_size_pct=1.0,
            invalidation_level=49500.0,
        ),
        htf_trend="bullish",
        session="london",
        scenario_detail="bos_continuation | long | close_confirm",
        timestamp=now,
    )


def _neutral_htf(symbol: str = "BTC/USDT") -> StructureContext:
    ctx = StructureContext(symbol=symbol, timeframe="1h")
    # No structure labels → neutral
    return ctx


def _bullish_htf(symbol: str = "BTC/USDT") -> StructureContext:
    ctx = StructureContext(symbol=symbol, timeframe="1h")
    ctx.structure_labels = ["HH", "HL", "HH", "HL"]
    return ctx


def _ltf(symbol: str = "BTC/USDT") -> StructureContext:
    return StructureContext(symbol=symbol, timeframe="15m")


def test_htf_neutral_hard_filter():
    """HTF neutral → pipeline erken çıkış, sinyal yok."""
    pipe = Pipeline(enabled_scenarios=["bos_continuation"])
    result = asyncio.run(pipe.run(_neutral_htf(), _ltf()))
    assert result == []


def test_htf_bearish_no_long():
    """HTF bearish → long setup pipeline'a girmiyor."""
    bearish_htf = StructureContext(symbol="BTC/USDT", timeframe="1h")
    bearish_htf.structure_labels = ["LL", "LH", "LL", "LH"]
    pipe = Pipeline(enabled_scenarios=["bos_continuation"])
    result = asyncio.run(pipe.run(bearish_htf, _ltf()))
    assert result == []
    # No long setups created
    for setups in pipe.active_setups.values():
        for s in setups:
            assert s.direction != "long"


def test_confluence_merge():
    """Aynı sembol/yönde 2 sinyal → tek birleşik sinyal."""
    pipe = Pipeline()
    signals = [
        _make_alert("BTC/USDT", "long", score=70),
        _make_alert("BTC/USDT", "long", score=75),
    ]
    merged = pipe._merge_confluence(signals)
    assert len(merged) == 1
    assert merged[0].score == 75


def test_confluence_different_symbols_not_merged():
    """Farklı semboller merge edilmez."""
    pipe = Pipeline()
    signals = [
        _make_alert("BTC/USDT", "long", score=70),
        _make_alert("ETH/USDT", "long", score=75),
    ]
    merged = pipe._merge_confluence(signals)
    assert len(merged) == 2


def test_cooldown():
    """Cooldown aktifken aynı sembol için sinyal gönderilmez."""
    from datetime import timedelta
    pipe = Pipeline(cooldown_minutes=5)
    # Set cooldown on BTC/USDT
    pipe.alert_cooldowns["BTC/USDT"] = datetime.now(timezone.utc) - timedelta(minutes=1)
    assert pipe._is_on_cooldown("BTC/USDT") is True
    assert pipe._is_on_cooldown("ETH/USDT") is False
