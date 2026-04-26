from __future__ import annotations

from statistics import mean

from core.candle import Candle
from core.context import StructureContext


def _candle_range(c: Candle) -> float:
    return max(c.high - c.low, 1e-9)


def _body_ratio(c: Candle) -> float:
    return abs(c.close - c.open) / _candle_range(c)


def _overlaps_zone(c: Candle, zone_low: float, zone_high: float, pad: float = 0.0) -> bool:
    return c.low <= (zone_high + pad) and c.high >= (zone_low - pad)


def _avg_range(candles: list[Candle], lookback: int = 10) -> float:
    if len(candles) < 2:
        return 0.0
    window = candles[-lookback:]
    return mean(_candle_range(c) for c in window)


def _latest_fvg_zone(ctx: StructureContext, direction: str) -> tuple[float, float, str] | None:
    from datetime import timezone
    wanted = "long" if direction == "long" else "short"
    for fvg in reversed(ctx.active_fvgs):
        if fvg.direction != wanted:
            continue
        ts = int(fvg.created_at.replace(tzinfo=timezone.utc).timestamp())
        return fvg.low, fvg.high, f"fvg:{wanted}:{ts}:{round(fvg.low, 6)}:{round(fvg.high, 6)}"
    return None


def _order_block_zone(
    candles: list[Candle], direction: str, displacement_idx: int
) -> tuple[float, float, str] | None:
    start = max(0, displacement_idx - 10)
    for idx in range(displacement_idx - 1, start - 1, -1):
        c = candles[idx]
        if direction == "long" and c.close < c.open:
            return c.low, c.high, f"ob:bull:{idx}"
        if direction == "short" and c.close > c.open:
            return c.low, c.high, f"ob:bear:{idx}"
    if displacement_idx < len(candles):
        d = candles[displacement_idx]
        return d.low, d.high, f"disp:{direction}:{displacement_idx}"
    return None


def _fib_zone(
    candles: list[Candle], direction: str, displacement_idx: int
) -> tuple[float, float, str] | None:
    start = max(0, displacement_idx - 12)
    impulse = candles[start : displacement_idx + 1]
    if not impulse:
        return None
    hi = max(c.high for c in impulse)
    lo = min(c.low for c in impulse)
    size = max(hi - lo, 1e-9)
    if direction == "long":
        z_low = hi - (size * 0.618)
        z_high = hi - (size * 0.5)
    else:
        z_low = lo + (size * 0.5)
        z_high = lo + (size * 0.618)
    return min(z_low, z_high), max(z_low, z_high), f"fib:{direction}:{displacement_idx}"


def _breakout_retest_zone(
    ctx: StructureContext, direction: str
) -> tuple[float, float, str] | None:
    wanted = "bullish" if direction == "long" else "bearish"
    for evt in reversed(ctx.bos_events):
        if evt.direction != wanted:
            continue
        pad = max(_avg_range(ctx.candles, 12) * 0.15, 1e-9)
        return (
            evt.level - pad,
            evt.level + pad,
            f"retest:{wanted}:{evt.candle_index}:{round(evt.level, 6)}",
        )
    return None


def _select_zone(
    ctx: StructureContext, direction: str, displacement_idx: int
) -> tuple[float, float, str] | None:
    return (
        _latest_fvg_zone(ctx, direction)
        or _order_block_zone(ctx.candles, direction, displacement_idx)
        or _breakout_retest_zone(ctx, direction)
        or _fib_zone(ctx.candles, direction, displacement_idx)
    )


def _detect_displacement_idx(ctx: StructureContext, direction: str) -> int | None:
    candles = ctx.candles
    if len(candles) < 12:
        return None
    for i in range(len(candles) - 2, 7, -1):
        c = candles[i]
        prev = candles[i - 8 : i]
        avg_r = mean(_candle_range(x) for x in prev)
        if _candle_range(c) <= avg_r * 1.5:
            continue
        if _body_ratio(c) < 0.6:
            continue
        if direction == "long" and c.close > c.open:
            return i
        if direction == "short" and c.close < c.open:
            return i
    return None


def _htf_trend(ctx: StructureContext) -> str:
    if ctx.htf_trend in {"bullish", "bearish"}:
        return ctx.htf_trend

    labels = ctx.external_structure_labels[-6:] or ctx.structure_labels[-6:]
    if labels:
        bullish = sum(1 for x in labels if x in {"HH", "HL"})
        bearish = sum(1 for x in labels if x in {"LL", "LH"})
        if bullish >= 4 and bullish > bearish:
            return "bullish"
        if bearish >= 4 and bearish > bullish:
            return "bearish"

    if len(ctx.candles) < 20:
        return "neutral"
    price = ctx.candles[-1].close
    ma = mean(c.close for c in ctx.candles[-20:])
    recent_high = max(c.high for c in ctx.candles[-20:])
    recent_low = min(c.low for c in ctx.candles[-20:])
    midpoint = (recent_high + recent_low) / 2
    if price > ma and price > midpoint:
        return "bullish"
    return "neutral"


def _pullback_active(ltf: StructureContext, trend: str) -> bool:
    labels = ltf.structure_labels[-6:]
    if len(labels) < 3:
        return False
    bearish_votes = sum(1 for x in labels if x in {"LL", "LH"})
    bullish_votes = sum(1 for x in labels if x in {"HH", "HL"})
    if trend == "bullish":
        return bearish_votes >= 3 and labels[-1] in {"LL", "LH"}
    return bullish_votes >= 3 and labels[-1] in {"HH", "HL"}


def _micro_bos_level(
    ltf: StructureContext, direction: str, displacement_idx: int
) -> float | None:
    if direction == "long":
        highs = [x.price for x in ltf.swing_highs if x.index > displacement_idx]
        return highs[-1] if highs else None
    lows = [x.price for x in ltf.swing_lows if x.index > displacement_idx]
    return lows[-1] if lows else None


def _still_against_entry(ltf: StructureContext, direction: str) -> bool:
    labels = ltf.structure_labels[-2:]
    if len(labels) < 2:
        return False
    if direction == "long":
        return labels[-1] == "LL"
    return labels[-1] == "HH"
