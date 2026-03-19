from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from core.candle import Candle
from core.models import FairValueGap, LiquidityZone, Range, SwingPoint, VolumeSpike


Direction = Literal["bullish", "bearish", "neutral"]
StructureLabel = Literal["HH", "HL", "LH", "LL"]


@dataclass
class SwingDetectionResult:
    swing_highs: list[SwingPoint] = field(default_factory=list)
    swing_lows: list[SwingPoint] = field(default_factory=list)
    equal_high_levels: list[float] = field(default_factory=list)
    equal_low_levels: list[float] = field(default_factory=list)


@dataclass
class StructureLabelResult:
    labels: list[StructureLabel] = field(default_factory=list)
    labeled_swings: list[tuple[SwingPoint, StructureLabel]] = field(default_factory=list)
    last_lh: SwingPoint | None = None
    last_hl: SwingPoint | None = None


@dataclass
class HtfStructureShiftResult:
    new_trend: Direction
    previous_trend: Direction
    broken_level: float
    broken_swing: SwingPoint
    direction: Literal["bullish", "bearish"]
    structure_type: Literal["LH", "HL"]
    reason: str


# ---------------------------------------------------------------------------
# Existing detection helpers
# ---------------------------------------------------------------------------


def _is_near_equal(a: float, b: float, tolerance_pct: float) -> bool:
    tol = max(max(abs(a), abs(b)) * max(tolerance_pct, 0.0), 1e-9)
    return abs(a - b) <= tol


def _true_range(curr: Candle, prev: Candle) -> float:
    return max(
        curr.high - curr.low,
        abs(curr.high - prev.close),
        abs(curr.low - prev.close),
    )


def _atr_series(candles: list[Candle], period: int) -> list[float]:
    if not candles:
        return []
    if len(candles) == 1:
        return [max(candles[0].high - candles[0].low, 1e-9)]

    tr_values: list[float] = [max(candles[0].high - candles[0].low, 1e-9)]
    for i in range(1, len(candles)):
        tr_values.append(max(_true_range(candles[i], candles[i - 1]), 1e-9))

    out: list[float] = []
    for i in range(len(candles)):
        start = max(0, i - period + 1)
        window = tr_values[start : i + 1]
        out.append(sum(window) / len(window))
    return out


def _raw_confirmed_pivots(candles: list[Candle], pivot_length: int) -> list[SwingPoint]:
    if pivot_length < 1:
        raise ValueError("pivot_length must be >= 1")
    if len(candles) < (2 * pivot_length + 1):
        return []

    pivots: list[SwingPoint] = []
    for i in range(pivot_length, len(candles) - pivot_length):
        pivot = candles[i]
        left = candles[i - pivot_length : i]
        right = candles[i + 1 : i + 1 + pivot_length]

        is_high = all(pivot.high > c.high for c in left) and all(pivot.high > c.high for c in right)
        is_low = all(pivot.low < c.low for c in left) and all(pivot.low < c.low for c in right)

        if is_high:
            pivots.append(SwingPoint(index=i, price=pivot.high, kind="high", timestamp=pivot.timestamp))
        if is_low:
            pivots.append(SwingPoint(index=i, price=pivot.low, kind="low", timestamp=pivot.timestamp))

    pivots.sort(key=lambda x: x.index)
    return pivots


def _follow_through_strength(
    candles: list[Candle],
    pivot: SwingPoint,
    pivot_length: int,
) -> tuple[float, float]:
    follow_window = candles[pivot.index + 1 : pivot.index + 1 + max(pivot_length, 1)]
    if not follow_window:
        return 0.0, 0.0

    if pivot.kind == "high":
        in_direction = max(pivot.price - min(c.low for c in follow_window), 0.0)
        against_direction = max(max(c.high for c in follow_window) - pivot.price, 0.0)
        return in_direction, against_direction

    in_direction = max(max(c.high for c in follow_window) - pivot.price, 0.0)
    against_direction = max(pivot.price - min(c.low for c in follow_window), 0.0)
    return in_direction, against_direction


def detect_confirmed_swings(
    candles: list[Candle],
    *,
    pivot_length: int,
    atr_period: int = 14,
    min_swing_distance_atr_mult: float = 0.8,
    structure_impact_atr_mult: float = 0.6,
    displacement_atr_mult: float = 0.8,
    equal_level_tolerance: float = 0.001,
) -> SwingDetectionResult:
    """Detect confirmed pivots and keep only structure-relevant swings.

    Filtering layers:
    1) confirmed left/right pivots
    2) same-type min distance (ATR based)
    3) structure impact or directional follow-through
    4) near-equal levels are tracked separately as liquidity pools
    """
    raw = _raw_confirmed_pivots(candles, pivot_length)
    if not raw:
        return SwingDetectionResult()

    atr = _atr_series(candles, atr_period)

    accepted: list[SwingPoint] = []
    highs: list[SwingPoint] = []
    lows: list[SwingPoint] = []
    equal_high_levels: list[float] = []
    equal_low_levels: list[float] = []

    last_high: SwingPoint | None = None
    last_low: SwingPoint | None = None

    for pivot in raw:
        atr_at_pivot = atr[pivot.index] if pivot.index < len(atr) else max(candles[pivot.index].high - candles[pivot.index].low, 1e-9)
        atr_at_pivot = max(atr_at_pivot, 1e-9)

        prev_same = last_high if pivot.kind == "high" else last_low
        prev_opp = last_low if pivot.kind == "high" else last_high

        if prev_same is not None:
            distance = abs(pivot.price - prev_same.price)
            min_required_distance = atr_at_pivot * max(min_swing_distance_atr_mult, 0.0)
            if distance < min_required_distance:
                if _is_near_equal(pivot.price, prev_same.price, equal_level_tolerance):
                    midpoint = (pivot.price + prev_same.price) / 2
                    if pivot.kind == "high":
                        equal_high_levels.append(midpoint)
                    else:
                        equal_low_levels.append(midpoint)
                continue

        in_direction, against_direction = _follow_through_strength(candles, pivot, pivot_length)
        follow_through_ok = (
            in_direction >= atr_at_pivot * max(displacement_atr_mult, 0.0)
            and in_direction >= against_direction
        )

        impact_ok = True
        if prev_opp is not None:
            impact_distance = abs(pivot.price - prev_opp.price)
            impact_ok = impact_distance >= atr_at_pivot * max(structure_impact_atr_mult, 0.0)

        if not (impact_ok or follow_through_ok):
            continue

        accepted.append(pivot)
        if pivot.kind == "high":
            highs.append(pivot)
            last_high = pivot
        else:
            lows.append(pivot)
            last_low = pivot

    # Also mark near-equal accepted swings as liquidity levels.
    for i in range(1, len(highs)):
        if _is_near_equal(highs[i].price, highs[i - 1].price, equal_level_tolerance):
            equal_high_levels.append((highs[i].price + highs[i - 1].price) / 2)
    for i in range(1, len(lows)):
        if _is_near_equal(lows[i].price, lows[i - 1].price, equal_level_tolerance):
            equal_low_levels.append((lows[i].price + lows[i - 1].price) / 2)

    # Stable unique ordering.
    eq_high_unique = sorted({round(x, 8): x for x in equal_high_levels}.values())
    eq_low_unique = sorted({round(x, 8): x for x in equal_low_levels}.values())

    return SwingDetectionResult(
        swing_highs=highs,
        swing_lows=lows,
        equal_high_levels=eq_high_unique,
        equal_low_levels=eq_low_unique,
    )


def classify_structure_labels(
    swing_highs: list[SwingPoint],
    swing_lows: list[SwingPoint],
    *,
    equal_level_tolerance: float = 0.001,
) -> StructureLabelResult:
    """Classify structure swings into HH/HL/LH/LL with correct same-type comparisons."""
    events = sorted([*swing_highs, *swing_lows], key=lambda x: x.index)

    labels: list[StructureLabel] = []
    labeled_swings: list[tuple[SwingPoint, StructureLabel]] = []

    prev_high: SwingPoint | None = None
    prev_low: SwingPoint | None = None
    last_lh: SwingPoint | None = None
    last_hl: SwingPoint | None = None

    for swing in events:
        if swing.kind == "high":
            if prev_high is None:
                prev_high = swing
                continue
            if _is_near_equal(swing.price, prev_high.price, equal_level_tolerance):
                prev_high = swing
                continue

            label: StructureLabel = "HH" if swing.price > prev_high.price else "LH"
            labels.append(label)
            labeled_swings.append((swing, label))
            if label == "LH":
                last_lh = swing
            prev_high = swing
            continue

        if prev_low is None:
            prev_low = swing
            continue
        if _is_near_equal(swing.price, prev_low.price, equal_level_tolerance):
            prev_low = swing
            continue

        label = "HL" if swing.price > prev_low.price else "LL"
        labels.append(label)
        labeled_swings.append((swing, label))
        if label == "HL":
            last_hl = swing
        prev_low = swing

    return StructureLabelResult(
        labels=labels,
        labeled_swings=labeled_swings,
        last_lh=last_lh,
        last_hl=last_hl,
    )


def detect_htf_structure_shift(
    *,
    candle: Candle,
    previous_trend: Direction,
    last_external_lh: SwingPoint | None,
    last_external_hl: SwingPoint | None,
    use_close_for_break_confirmation: bool = True,
) -> HtfStructureShiftResult | None:
    break_up_value = candle.close if use_close_for_break_confirmation else candle.high
    break_down_value = candle.close if use_close_for_break_confirmation else candle.low

    broke_lh = last_external_lh is not None and break_up_value > last_external_lh.price
    broke_hl = last_external_hl is not None and break_down_value < last_external_hl.price

    if broke_lh and broke_hl:
        # Ambiguous candle that sweeps both directions — do not force a trend flip.
        return None

    if broke_lh and previous_trend in {"bearish", "neutral"}:
        return HtfStructureShiftResult(
            new_trend="bullish",
            previous_trend=previous_trend,
            broken_level=last_external_lh.price,
            broken_swing=last_external_lh,
            direction="bullish",
            structure_type="LH",
            reason=(
                f"{candle.timeframe} close broke last external LH ({last_external_lh.price:.6f})"
                if use_close_for_break_confirmation
                else f"{candle.timeframe} high broke last external LH ({last_external_lh.price:.6f})"
            ),
        )

    if broke_hl and previous_trend in {"bullish", "neutral"}:
        return HtfStructureShiftResult(
            new_trend="bearish",
            previous_trend=previous_trend,
            broken_level=last_external_hl.price,
            broken_swing=last_external_hl,
            direction="bearish",
            structure_type="HL",
            reason=(
                f"{candle.timeframe} close broke last external HL ({last_external_hl.price:.6f})"
                if use_close_for_break_confirmation
                else f"{candle.timeframe} low broke last external HL ({last_external_hl.price:.6f})"
            ),
        )

    return None


def detect_swing(candles: list[Candle], lookback: int = 2) -> tuple[SwingPoint | None, SwingPoint | None]:
    """Backward-compatible helper that returns the latest confirmed pivot pair."""
    result = detect_confirmed_swings(
        candles,
        pivot_length=lookback,
        min_swing_distance_atr_mult=0.0,
        structure_impact_atr_mult=0.0,
        displacement_atr_mult=0.0,
        equal_level_tolerance=0.0,
    )
    high = result.swing_highs[-1] if result.swing_highs else None
    low = result.swing_lows[-1] if result.swing_lows else None
    return high, low


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


def market_direction(labels: list[str]) -> Direction:
    if len(labels) < 3:
        return "neutral"
    last = labels[-6:]
    bullish_votes = sum(1 for x in last if x in {"HH", "HL"})
    bearish_votes = sum(1 for x in last if x in {"LL", "LH"})
    total = bullish_votes + bearish_votes
    if total == 0:
        return "neutral"
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
    """Return index of the most recent displacement candle, else None."""
    if len(candles) < lookback + 1:
        return None
    for i in range(len(candles) - 1, lookback - 1, -1):
        prev = candles[i - lookback : i]
        avg_body = sum(abs(c.close - c.open) for c in prev) / len(prev)
        avg_vol = sum(c.volume for c in prev) / len(prev)
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
