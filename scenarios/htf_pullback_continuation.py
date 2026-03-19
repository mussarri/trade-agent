from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean

from core.candle import Candle
from core.context import StructureContext
from core.models import Setup, Trigger, TriggerCondition
from scenarios.base import BaseScenario


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
    wanted = "long" if direction == "long" else "short"
    for fvg in reversed(ctx.active_fvgs):
        if fvg.direction != wanted:
            continue
        ts = int(fvg.created_at.replace(tzinfo=timezone.utc).timestamp())
        return fvg.low, fvg.high, f"fvg:{wanted}:{ts}:{round(fvg.low, 6)}:{round(fvg.high, 6)}"
    return None


def _order_block_zone(candles: list[Candle], direction: str, displacement_idx: int) -> tuple[float, float, str] | None:
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


def _fib_zone(candles: list[Candle], direction: str, displacement_idx: int) -> tuple[float, float, str] | None:
    start = max(0, displacement_idx - 12)
    impulse = candles[start:displacement_idx + 1]
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


def _breakout_retest_zone(ctx: StructureContext, direction: str) -> tuple[float, float, str] | None:
    wanted = "bullish" if direction == "long" else "bearish"
    for evt in reversed(ctx.bos_events):
        if evt.direction != wanted:
            continue
        pad = max(_avg_range(ctx.candles, 12) * 0.15, 1e-9)
        return evt.level - pad, evt.level + pad, f"retest:{wanted}:{evt.candle_index}:{round(evt.level, 6)}"
    return None


def _select_zone(ctx: StructureContext, direction: str, displacement_idx: int) -> tuple[float, float, str] | None:
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
        prev = candles[i - 8:i]
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


def _micro_bos_level(ltf: StructureContext, direction: str, displacement_idx: int) -> float | None:
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


class HtfPullbackContinuationScenario(BaseScenario):
    name = "htf_pullback_continuation"
    alert_type = "SETUP_DETECTED"

    def detect_setup(self, htf_ctx: StructureContext, ltf_ctx: StructureContext) -> Setup | None:
        if htf_ctx.timeframe != "1h" or ltf_ctx.timeframe != "5m":
            return None
        if not ltf_ctx.candles:
            return None

        trend = _htf_trend(htf_ctx)
        if trend not in {"bullish", "bearish"}:
            return None

        direction = "long" if trend == "bullish" else "short"
        if not _pullback_active(ltf_ctx, trend):
            return None

        displacement_idx = _detect_displacement_idx(ltf_ctx, direction)
        if displacement_idx is None:
            return None

        zone = _select_zone(ltf_ctx, direction, displacement_idx)
        if zone is None:
            return None
        zone_low, zone_high, zone_id = zone

        last = ltf_ctx.candles[-1]
        pad = max(_avg_range(ltf_ctx.candles, 10) * 0.1, 1e-9)
        if not _overlaps_zone(last, zone_low, zone_high, pad=pad):
            return None

        # First pullback rule: current zone touch must be the first touch after displacement.
        prior_touches = 0
        for c in ltf_ctx.candles[displacement_idx + 1:-1]:
            if _overlaps_zone(c, zone_low, zone_high):
                prior_touches += 1
        if prior_touches > 0:
            return None

        micro_level = _micro_bos_level(ltf_ctx, direction, displacement_idx)
        if micro_level is None:
            return None

        pullback = ltf_ctx.candles[displacement_idx + 1:] or [last]
        swing_low = min(c.low for c in pullback)
        swing_high = max(c.high for c in pullback)
        invalidation = swing_low if direction == "long" else swing_high
        setup_id = f"{ltf_ctx.symbol}:{zone_id}:{trend}"

        return Setup(
            scenario_name=self.name,
            alert_type="SETUP_DETECTED",
            symbol=ltf_ctx.symbol,
            timeframe=ltf_ctx.timeframe,
            direction=direction,
            entry_zone_low=zone_low,
            entry_zone_high=zone_high,
            swing_low=swing_low,
            swing_high=swing_high,
            invalidation_level=invalidation,
            max_candles=24,
            meta={
                "state": "NEW",
                "trend": trend,
                "zone_id": zone_id,
                "setup_id": setup_id,
                "micro_bos_level": micro_level,
                "displacement_idx": displacement_idx,
            },
        )

    def detect_trigger(self, setup: Setup, ltf_ctx: StructureContext) -> Trigger | None:
        if not ltf_ctx.candles:
            return None
        last = ltf_ctx.candles[-1]
        trend = setup.meta.get("trend")
        zone_low, zone_high = setup.entry_zone_low, setup.entry_zone_high
        near_zone = _overlaps_zone(last, zone_low, zone_high, pad=max(_avg_range(ltf_ctx.candles, 10) * 0.2, 1e-9))
        if not near_zone:
            return None

        avg_r = _avg_range(ltf_ctx.candles[:-1], 10) if len(ltf_ctx.candles) > 2 else _avg_range(ltf_ctx.candles, 10)
        candle_is_bull = last.close > last.open and _body_ratio(last) >= 0.6
        candle_is_bear = last.close < last.open and _body_ratio(last) >= 0.6
        displacement_ok = _candle_range(last) > avg_r * 1.5 if avg_r > 0 else False
        zone_mid = (zone_low + zone_high) / 2
        reacted = (last.close > zone_mid and last.low <= zone_high) if setup.direction == "long" else (last.close < zone_mid and last.high >= zone_low)
        micro_level = float(setup.meta.get("micro_bos_level", 0.0))

        if setup.direction == "long":
            micro_bos = last.close > micro_level
            directional_body = candle_is_bull
        else:
            micro_bos = last.close < micro_level
            directional_body = candle_is_bear

        strict_ok = (
            not _still_against_entry(ltf_ctx, setup.direction)
            and reacted
            and displacement_ok
            and directional_body
            and micro_bos
        )
        if not strict_ok:
            return None

        setup.alert_type = "ENTRY_CONFIRMED"
        setup.meta["state"] = "TRIGGERED"
        setup.meta["trend"] = trend
        setup.meta["entry_price"] = last.close
        return Trigger(
            setup=setup,
            conditions=TriggerCondition(
                close_confirm=reacted,
                breakout_close=micro_bos,
                displacement_confirm=displacement_ok,
            ),
            confidence_factors={
                "htf_alignment": trend in {"bullish", "bearish"},
                "pullback_active": True,
                "zone_reaction": reacted,
                "displacement": displacement_ok,
                "micro_bos": micro_bos,
                "first_pullback": True,
            },
            timestamp=last.timestamp,
        )

    def is_invalidated(self, setup: Setup, ltf_ctx: StructureContext) -> bool:
        if not ltf_ctx.candles:
            return False
        if setup.candles_elapsed >= setup.max_candles:
            setup.meta["state"] = "EXPIRED"
            return True
        last = ltf_ctx.candles[-1]
        if setup.direction == "long" and last.close < setup.invalidation_level:
            setup.meta["state"] = "EXPIRED"
            return True
        if setup.direction == "short" and last.close > setup.invalidation_level:
            setup.meta["state"] = "EXPIRED"
            return True
        return False
