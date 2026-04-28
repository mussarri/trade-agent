from __future__ import annotations

from core.context import StructureContext
from core.models import Setup, Trigger, TriggerCondition
from scenarios._ict_helpers import (
    _avg_range,
    _body_ratio,
    _candle_range,
    _detect_displacement_idx,
    _htf_trend,
    _micro_bos_level,
    _overlaps_zone,
    _pullback_active,
    _select_zone,
    _still_against_entry,
)
from scenarios.base import BaseScenario


class Forex1hPullbackScenario(BaseScenario):
    """HTF pullback continuation strategy adapted for a single Twelve Data timeframe.

    Used for instruments sourced from Twelve Data (XAU/USD, EUR/USD, etc.).
    Passes the same StructureContext as both htf_ctx and ltf_ctx:
    - external_structure_labels → trend (longer pivot = "HTF" proxy)
    - internal structure_labels → pullback detection ("LTF" proxy)
    """

    name = "forex_1h_pullback"
    alert_type = "SETUP_DETECTED"
    supported_timeframes = {"1h", "5min"}

    def detect_setup(self, htf_ctx: StructureContext, ltf_ctx: StructureContext) -> Setup | None:
        if ltf_ctx.timeframe not in self.supported_timeframes:
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

        prior_touches = 0
        for c in ltf_ctx.candles[displacement_idx + 1 : -1]:
            if _overlaps_zone(c, zone_low, zone_high):
                prior_touches += 1
        if prior_touches > 0:
            return None

        micro_level = _micro_bos_level(ltf_ctx, direction, displacement_idx)
        if micro_level is None:
            return None

        pullback = ltf_ctx.candles[displacement_idx + 1 :] or [last]
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
            max_candles=20,
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
        near_zone = _overlaps_zone(
            last,
            zone_low,
            zone_high,
            pad=max(_avg_range(ltf_ctx.candles, 10) * 0.2, 1e-9),
        )
        if not near_zone:
            return None

        avg_r = (
            _avg_range(ltf_ctx.candles[:-1], 10)
            if len(ltf_ctx.candles) > 2
            else _avg_range(ltf_ctx.candles, 10)
        )
        candle_is_bull = last.close > last.open and _body_ratio(last) >= 0.6
        candle_is_bear = last.close < last.open and _body_ratio(last) >= 0.6
        displacement_ok = _candle_range(last) > avg_r * 1.5 if avg_r > 0 else False
        zone_mid = (zone_low + zone_high) / 2
        reacted = (
            (last.close > zone_mid and last.low <= zone_high)
            if setup.direction == "long"
            else (last.close < zone_mid and last.high >= zone_low)
        )
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
