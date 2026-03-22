from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from alerts.base import BaseAlert
from core.context import StructureContext
from core.models import Setup, Trigger, TriggerCondition
from core.pipeline import Pipeline
from scenarios.base import BaseScenario


class _CapturingAlert(BaseAlert):
    def __init__(self) -> None:
        self.payload_types: list[type] = []
        self.setup_count = 0
        self.structure_count = 0

    async def send(self, payload: dict) -> None:
        self.payload_types.append(type(payload))

    async def send_setup(self, payload: dict) -> None:
        self.setup_count += 1

    async def send_structure(self, payload: dict) -> None:
        self.structure_count += 1


class _AlwaysTriggerScenario(BaseScenario):
    name = "htf_pullback_continuation"
    alert_type = "SETUP_DETECTED"

    def detect_setup(self, htf_ctx, ltf_ctx):
        if not ltf_ctx.candles:
            return None
        return Setup(
            scenario_name=self.name,
            alert_type=self.alert_type,
            symbol=ltf_ctx.symbol,
            timeframe=ltf_ctx.timeframe,
            direction="long",
            entry_zone_low=99.0,
            entry_zone_high=101.0,
            swing_low=98.0,
            swing_high=103.0,
            invalidation_level=97.0,
            max_candles=10,
            meta={
                "trend": "bullish",
                "zone_id": "zone-1",
                "setup_id": f"{ltf_ctx.symbol}:zone-1:bullish",
            },
        )

    def detect_trigger(self, setup, ltf_ctx):
        c = ltf_ctx.candles[-1]
        return Trigger(
            setup=setup,
            conditions=TriggerCondition(close_confirm=True),
            confidence_factors={
                "htf_alignment": True,
                "pullback_active": True,
                "zone_reaction": True,
                "displacement": True,
                "micro_bos": True,
                "first_pullback": True,
            },
            timestamp=c.timestamp,
        )


def _htf_bullish(symbol: str = "BTC/USDT") -> StructureContext:
    ctx = StructureContext(symbol=symbol, timeframe="1h")
    ctx.external_structure_labels = ["HH", "HL", "HH"]
    return ctx


def _ltf(symbol: str = "BTC/USDT", tf: str = "15m") -> StructureContext:
    from core.candle import Candle

    ctx = StructureContext(symbol=symbol, timeframe=tf, is_ltf=True)
    now = datetime.now(tz=timezone.utc)
    for i in range(20):
        ctx.candles.append(
            Candle(
                symbol=symbol,
                timeframe=tf,
                timestamp=now,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.2,
                volume=100 + i,
                is_closed=True,
            )
        )
    return ctx


def test_cooldown_is_scenario_and_timeframe_specific():
    pipe = Pipeline()
    pipe._set_cooldown("BTC/USDT", "htf_pullback_continuation", "15m", "long")
    assert pipe._is_on_cooldown("BTC/USDT", "htf_pullback_continuation", "15m", "long") is True
    assert pipe._is_on_cooldown("BTC/USDT", "other", "15m", "long") is False
    assert pipe._is_on_cooldown("BTC/USDT", "htf_pullback_continuation", "5m", "long") is False


def test_signal_store_insertion_and_alert_payload_dict():
    alert = _CapturingAlert()
    pipe = Pipeline(min_score=0, min_rr_ratio=0, alerts=[alert], enabled_scenarios=[])
    pipe.scenarios = [_AlwaysTriggerScenario()]
    htf = _htf_bullish()
    ltf = _ltf()

    result = asyncio.run(pipe.run(htf, ltf))
    assert len(result) == 1
    assert len(pipe.signal_store.active_signals) == 1
    assert alert.payload_types == [dict]
    assert alert.setup_count == 1


def test_setup_and_entry_are_deduplicated():
    alert = _CapturingAlert()
    pipe = Pipeline(min_score=0, min_rr_ratio=0, alerts=[alert], enabled_scenarios=[])
    pipe.scenarios = [_AlwaysTriggerScenario()]
    htf = _htf_bullish()
    ltf = _ltf()

    first = asyncio.run(pipe.run(htf, ltf))
    second = asyncio.run(pipe.run(htf, ltf))

    assert len(first) == 1
    assert len(second) == 0
    assert alert.setup_count == 1
    assert len(pipe.signal_store.history) == 1


def test_pipeline_dispatches_htf_structure_shift_alerts():
    from core.candle import Candle
    from core.models import SwingPoint

    alert = _CapturingAlert()
    pipe = Pipeline(min_score=0, min_rr_ratio=0, alerts=[alert], enabled_scenarios=[])

    htf = StructureContext(symbol="BTC/USDT", timeframe="1h")
    htf.htf_trend = "bearish"
    htf.last_external_lh = SwingPoint(index=10, price=100.0, kind="high")
    htf._update_htf_trend(
        Candle(
            symbol="BTC/USDT",
            timeframe="1h",
            timestamp=datetime.now(tz=timezone.utc),
            open=99.5,
            high=101.2,
            low=99.0,
            close=100.8,
            volume=120.0,
            is_closed=True,
        )
    )

    ltf = _ltf()
    result = asyncio.run(pipe.run(htf, ltf))
    assert result == []
    assert alert.structure_count == 1


def test_pipeline_dispatches_ltf_5m_breakout_alerts():
    from core.candle import Candle

    alert = _CapturingAlert()
    pipe = Pipeline(min_score=0, min_rr_ratio=0, alerts=[alert], enabled_scenarios=[])

    htf = _htf_bullish()
    ltf = _ltf(tf="5m")
    ltf._append_bos_if_new(
        candle=Candle(
            symbol="BTC/USDT",
            timeframe="5m",
            timestamp=datetime.now(tz=timezone.utc),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.9,
            volume=110.0,
            is_closed=True,
        ),
        direction="bullish",
        level=100.5,
        structure_kind="internal",
        displacement=False,
    )

    result = asyncio.run(pipe.run(htf, ltf))
    assert result == []
    assert alert.structure_count == 1
