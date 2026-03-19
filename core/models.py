from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Risk plan (moved here to avoid circular imports)
# ---------------------------------------------------------------------------

class RiskPlan(BaseModel):
    entry_low: float
    entry_high: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    rr_ratio: float
    position_size_pct: float
    invalidation_level: float


# ---------------------------------------------------------------------------
# Market-structure primitives
# ---------------------------------------------------------------------------

@dataclass
class SwingPoint:
    index: int
    price: float
    kind: Literal["high", "low"]
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class LiquidityZone:
    price: float
    kind: Literal["high", "low"]   # equal-high or equal-low cluster
    swept: bool = False


@dataclass
class FairValueGap:
    direction: Literal["long", "short"]
    low: float
    high: float
    midpoint: float
    active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class VolumeSpike:
    volume: float
    avg_volume: float
    ratio: float
    timestamp: datetime


@dataclass
class LiquiditySweepEvent:
    """Records when price sweeps a liquidity zone and rejects back inside.

    direction:
        "bullish" — sell-side liquidity swept (low zone broken, close recovered above).
                    Favours long setups.
        "bearish" — buy-side liquidity swept (high zone broken, close rejected below).
                    Favours short setups.
    """
    direction: Literal["bullish", "bearish"]
    price: float
    timestamp: datetime


@dataclass
class Range:
    high: float
    low: float
    midpoint: float
    bars: int = 0


# ---------------------------------------------------------------------------
# Two-stage scenario types
# ---------------------------------------------------------------------------

class TriggerCondition(BaseModel):
    close_confirm: bool = False
    displacement_confirm: bool = False
    breakout_close: bool = False


class Setup(BaseModel):
    scenario_name: str
    alert_type: str
    symbol: str
    timeframe: str
    direction: Literal["long", "short"]
    entry_zone_low: float
    entry_zone_high: float
    swing_low: float
    swing_high: float
    invalidation_level: float
    state: Literal["NEW", "ACTIVE", "TRIGGERED", "EXPIRED"] = "NEW"
    candles_elapsed: int = 0
    max_candles: int = 20
    meta: dict[str, Any] = Field(default_factory=dict)


class Trigger(BaseModel):
    setup: Setup
    conditions: TriggerCondition
    confidence_factors: dict[str, bool]
    timestamp: datetime


# ---------------------------------------------------------------------------
# Unified alert output
# ---------------------------------------------------------------------------

class AlertPayload(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: Literal["active"] = "active"
    type: Literal["SETUP_DETECTED", "ENTRY_CONFIRMED"] = "ENTRY_CONFIRMED"
    scenario_name: str
    alert_type: Literal["SETUP_DETECTED", "ENTRY_CONFIRMED"] = "ENTRY_CONFIRMED"
    symbol: str
    pair: str = ""          # "BTCUSDT" format for display
    timeframe: str          # LTF timeframe (e.g. "15m") — kept for backward compat
    timeframe_ltf: str = "" # same as timeframe, explicit field for frontend
    timeframe_htf: str = "" # HTF timeframe from settings (e.g. "1h", "4h")
    direction: Literal["long", "short"]
    score: int
    confidence_factors: dict[str, bool]
    risk_plan: RiskPlan
    ict_full_setup: bool = False
    htf_trend: str = ""
    session: str = ""
    scenario_detail: str = ""
    trend: Literal["bullish", "bearish", "neutral"] = "neutral"
    zone: list[float] = Field(default_factory=list)
    entry: float = 0.0
    sl: float = 0.0
    tp: list[float] = Field(default_factory=list)
    confidence: float = 0.0
    setup_id: str = ""
    zone_id: str = ""
    timestamp: datetime
