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

    async def send(self, payload: dict) -> None:
        self.payload_types.append(type(payload))


class _AlwaysTriggerScenario(BaseScenario):
    name = "always_trigger"
    alert_type = "ALWAYS_TRIGGER"

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
            meta={"has_fvg": True},
        )

    def detect_trigger(self, setup, ltf_ctx):
        c = ltf_ctx.candles[-1]
        return Trigger(
            setup=setup,
            conditions=TriggerCondition(close_confirm=True),
            confidence_factors={
                "htf_alignment": True,
                "fvg_presence": True,
                "volume_confirmation": False,
                "liquidity_confluence": False,
                "session_time": True,
            },
            timestamp=c.timestamp,
        )


def _htf_bullish(symbol: str = "BTC/USDT") -> StructureContext:
    ctx = StructureContext(symbol=symbol, timeframe="1h")
    ctx.external_structure_labels = ["HH", "HL", "HH"]
    return ctx


def _ltf(symbol: str = "BTC/USDT", tf: str = "15m") -> StructureContext:
    from core.candle import Candle

    ctx = StructureContext(symbol=symbol, timeframe=tf)
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
    pipe._set_cooldown("BTC/USDT", "bos_continuation", "15m", "long")
    assert pipe._is_on_cooldown("BTC/USDT", "bos_continuation", "15m", "long") is True
    assert pipe._is_on_cooldown("BTC/USDT", "fvg_retrace", "15m", "long") is False
    assert pipe._is_on_cooldown("BTC/USDT", "bos_continuation", "5m", "long") is False


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
