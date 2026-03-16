from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from core.candle import Candle
from core.models import LiquidityZone, Range, VolumeSpike


Direction = Literal["bullish", "bearish", "neutral"]


# ---------------------------------------------------------------------------
# Legacy dataclasses (kept for backward-compat with context.py)
# ---------------------------------------------------------------------------

@dataclass
class SwingPoint:
    index: int
    price: float
    kind: Literal["high", "low"]


@dataclass
class FairValueGap:
    direction: Literal["long", "short"]
    low: float
    high: float
    midpoint: float
    active: bool = True


# ---------------------------------------------------------------------------
# Existing detection helpers
# ---------------------------------------------------------------------------

def detect_swing(candles: list[Candle], lookback: int = 2) -> tuple[SwingPoint | None, SwingPoint | None]:
    if len(candles) < (2 * lookback + 1):
        return None, None

    idx = len(candles) - lookback - 1
    pivot = candles[idx]
    left = candles[idx - lookback : idx]
    right = candles[idx + 1 : idx + 1 + lookback]

    is_high = all(pivot.high > c.high for c in left + right)
    is_low = all(pivot.low < c.low for c in left + right)

    swing_high = SwingPoint(index=idx, price=pivot.high, kind="high") if is_high else None
    swing_low = SwingPoint(index=idx, price=pivot.low, kind="low") if is_low else None
    return swing_high, swing_low


def detect_fvg(candles: list[Candle]) -> FairValueGap | None:
    if len(candles) < 3:
        return None
    c1, _, c3 = candles[-3], candles[-2], candles[-1]

    if c1.high < c3.low:
        low, high = c1.high, c3.low
        return FairValueGap(direction="long", low=low, high=high, midpoint=(low + high) / 2)

    if c1.low > c3.high:
        low, high = c3.high, c1.low
        return FairValueGap(direction="short", low=low, high=high, midpoint=(low + high) / 2)

    return None


# market_direction() fonksiyonunu güncelle
def market_direction(labels: list[str]) -> Direction:
    if len(labels) < 3:
        return "neutral"
    last = labels[-6:]   # 4'ten 6'ya çıkar
    bullish_votes = sum(1 for x in last if x in {"HH", "HL"})
    bearish_votes = sum(1 for x in last if x in {"LL", "LH"})
    total = bullish_votes + bearish_votes
    if total == 0:
        return "neutral"
    # %60 çoğunluk yeterli — eskiden %100 gerekiyordu pratikte
    if bullish_votes / total >= 0.6:
        return "bullish"
    if bearish_votes / total >= 0.6:
        return "bearish"
    return "neutral"


# ---------------------------------------------------------------------------
# New detection helpers (Step 2 additions)
# ---------------------------------------------------------------------------

def detect_equal_levels(
    swing_points: list[SwingPoint],
    tolerance_pct: float = 0.001,
) -> list[LiquidityZone]:
    zones: list[LiquidityZone] = []
    for i in range(1, len(swing_points)):
        a, b = swing_points[i - 1], swing_points[i]
        tol = max(tolerance_pct * b.price, 1e-9)
        if abs(a.price - b.price) <= tol:
            zones.append(LiquidityZone(price=(a.price + b.price) / 2, kind=b.kind))
    return zones


def detect_volume_spike(
    candles: list[Candle],
    lookback: int = 20,
    threshold: float = 2.0,
) -> VolumeSpike | None:
    if len(candles) < lookback + 1:
        return None
    recent = candles[-lookback - 1 : -1]
    avg = sum(c.volume for c in recent) / len(recent)
    last = candles[-1]
    if avg > 0 and last.volume >= avg * threshold:
        return VolumeSpike(
            volume=last.volume,
            avg_volume=avg,
            ratio=last.volume / avg,
            timestamp=last.timestamp,
        )
    return None


def detect_range(
    candles: list[Candle],
    lookback: int = 30,
    tolerance_pct: float = 0.002,
) -> Range | None:
    if len(candles) < lookback:
        return None
    window = candles[-lookback:]
    high = max(c.high for c in window)
    low = min(c.low for c in window)
    spread_pct = (high - low) / max(low, 1e-9)
    if spread_pct <= tolerance_pct * 10:  # range if spread <= 2% (10× tolerance)
        return Range(high=high, low=low, midpoint=(high + low) / 2, bars=lookback)
    return None


def detect_sweep(candle: Candle, zones: list[LiquidityZone]) -> LiquidityZone | None:
    for zone in zones:
        if zone.swept:
            continue
        if zone.kind == "low" and candle.low < zone.price and candle.close > zone.price:
            return zone
        if zone.kind == "high" and candle.high > zone.price and candle.close < zone.price:
            return zone
    return None


def detect_displacement(
    candles: list[Candle],
    body_multiplier: float = 1.5,
    vol_multiplier: float = 1.2,
    lookback: int = 5,
) -> int | None:
    """Son mumu da dahil ederek geriye doğru tara.
    Body > body_multiplier × avg_body(önceki lookback mum) VE
    volume > vol_multiplier × avg_vol(önceki lookback mum)
    şartını sağlayan en son mumun indeksini döner. Yoksa None."""
    if len(candles) < lookback + 1:
        return None
    for i in range(len(candles) - 1, lookback - 1, -1):
        prev = candles[i - lookback : i]
        avg_body = sum(abs(c.close - c.open) for c in prev) / len(prev)
        avg_vol  = sum(c.volume for c in prev) / len(prev)
        body = abs(candles[i].close - candles[i].open)
        if avg_body > 0 and body >= avg_body * body_multiplier:
            if avg_vol > 0 and candles[i].volume >= avg_vol * vol_multiplier:
                return i
    return None


def calculate_atr(candles: list[Candle], period: int = 14) -> float:
    """Average True Range over the last `period` candles."""
    if len(candles) < 2:
        return (candles[0].high - candles[0].low) if candles else 0.0
    window = candles[-period:]
    tr_values = []
    for i in range(1, len(window)):
        tr_values.append(max(
            window[i].high - window[i].low,
            abs(window[i].high - window[i - 1].close),
            abs(window[i].low - window[i - 1].close),
        ))
    return sum(tr_values) / len(tr_values) if tr_values else 0.0


def current_session() -> str:
    """Return approximate trading session name based on UTC hour."""
    hour = datetime.now(timezone.utc).hour
    if 0 <= hour < 8:
        return "asian"
    if 8 <= hour < 12:
        return "london"
    if 12 <= hour < 13:
        return "overlap"
    if 13 <= hour < 21:
        return "new_york"
    return "off"
