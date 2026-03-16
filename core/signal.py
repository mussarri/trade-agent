from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from core.models import RiskPlan


class Signal(BaseModel):
    scenario_name: str
    symbol: str
    timeframe: str
    direction: str
    score: int
    confidence_factors: dict[str, bool]
    risk_plan: RiskPlan
    timestamp: datetime
