from __future__ import annotations

from abc import ABC
from datetime import datetime
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

from core.models import Setup, Trigger

if TYPE_CHECKING:
    from core.context import StructureContext


class ScenarioMatch(BaseModel):
    scenario_name: str
    symbol: str
    timeframe: str
    direction: Literal["long", "short"]
    confidence_factors: dict[str, bool]
    key_levels: dict[str, float]
    timestamp: datetime


class BaseScenario(ABC):
    name: str
    alert_type: str = ""

    def matches(self, htf_ctx: "StructureContext", ltf_ctx: "StructureContext") -> ScenarioMatch | None:
        """Legacy single-stage match — returns None by default."""
        return None

    def detect_setup(self, htf_ctx: "StructureContext", ltf_ctx: "StructureContext") -> Setup | None:
        """Stage 1: detect if market structure has formed a tradeable setup.

        Pipeline HTF alignment kontrolünü dışarıda yapıyor,
        burada tekrar kontrol etme.
        """
        return None

    def detect_trigger(self, setup: Setup, ltf_ctx: "StructureContext") -> Trigger | None:
        """Stage 2: given an active setup, check if entry trigger has fired."""
        return None

    def is_invalidated(self, setup: Setup, ltf_ctx: "StructureContext") -> bool:
        if not ltf_ctx.candles:
            return False
        last = ltf_ctx.candles[-1]
        if setup.direction == "long" and last.close < setup.invalidation_level:
            return True
        if setup.direction == "short" and last.close > setup.invalidation_level:
            return True
        if setup.candles_elapsed >= setup.max_candles:
            return True
        return False

    def describe(self, setup: Setup, trigger: Trigger) -> str:
        cond = trigger.conditions
        if cond.sweep_reversal:
            kind = "sweep_reversal"
        elif cond.close_confirm:
            kind = "close_confirm"
        elif cond.breakout_close:
            kind = "breakout_close"
        else:
            kind = "fvg_entered"
        ict_tag = " | ICT Full Setup" if setup.meta.get("ict_bonus") else ""
        return f"{self.name} | {setup.direction} | {kind}{ict_tag}"
