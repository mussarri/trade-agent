from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class Candle(BaseModel):
    symbol: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool = False
