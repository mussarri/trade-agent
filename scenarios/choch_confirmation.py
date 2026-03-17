from __future__ import annotations

from core.models import Setup, Trigger, TriggerCondition
from core.structure import calculate_atr, current_session
from scenarios.base import BaseScenario


class ChochConfirmationScenario(BaseScenario):
    """External CHoCH followed by same-direction BOS confirmation."""

    name = "choch_confirmation"
    alert_type = "CHOCH_CONFIRMATION"

    def detect_setup(self, htf_ctx, ltf_ctx) -> Setup | None:
        htf_trend = htf_ctx.trend
        if htf_trend == "neutral":
            return None
        last_choch = ltf_ctx.last_choch
        if not last_choch or last_choch.structure_kind != "external":
            return None

        direction = "long" if last_choch.direction == "bullish" else "short"
        if (htf_trend == "bullish" and direction != "long") or (htf_trend == "bearish" and direction != "short"):
            return None

        last_ext_bos = ltf_ctx.last_external_bos
        if not last_ext_bos or last_ext_bos.timestamp < last_choch.timestamp:
            return None
        if (direction == "long" and last_ext_bos.direction != "bullish") or (
            direction == "short" and last_ext_bos.direction != "bearish"
        ):
            return None

        atr = calculate_atr(ltf_ctx.candles) if ltf_ctx.candles else 0.0
        if atr <= 0:
            return None

        bos_level = last_ext_bos.level
        if direction == "long":
            watch_low = bos_level - atr * 0.25
            watch_high = bos_level + atr * 0.35
            invalidation = watch_low - atr * 0.8
            swing_low = ltf_ctx.swing_lows[-1].price if ltf_ctx.swing_lows else invalidation
            swing_high = ltf_ctx.swing_highs[-1].price if ltf_ctx.swing_highs else watch_high * 1.01
        else:
            watch_low = bos_level - atr * 0.35
            watch_high = bos_level + atr * 0.25
            invalidation = watch_high + atr * 0.8
            swing_low = ltf_ctx.swing_lows[-1].price if ltf_ctx.swing_lows else watch_low * 0.99
            swing_high = ltf_ctx.swing_highs[-1].price if ltf_ctx.swing_highs else invalidation

        if watch_low >= watch_high:
            return None

        return Setup(
            scenario_name=self.name,
            alert_type=self.alert_type,
            symbol=ltf_ctx.symbol,
            timeframe=ltf_ctx.timeframe,
            direction=direction,
            entry_zone_low=watch_low,
            entry_zone_high=watch_high,
            swing_low=swing_low,
            swing_high=swing_high,
            invalidation_level=invalidation,
            max_candles=16,
            meta={
                "choch_timestamp": last_choch.timestamp.isoformat(),
                "bos_level": bos_level,
            },
        )

    def detect_trigger(self, setup: Setup, ltf_ctx) -> Trigger | None:
        if not ltf_ctx.candles:
            return None
        c = ltf_ctx.candles[-1]
        midpoint = (setup.entry_zone_low + setup.entry_zone_high) / 2

        close_confirm = False
        breakout_close = False
        if setup.direction == "long":
            close_confirm = setup.entry_zone_low <= c.close <= setup.entry_zone_high and c.close >= midpoint
            breakout_close = c.close > setup.entry_zone_high
        else:
            close_confirm = setup.entry_zone_low <= c.close <= setup.entry_zone_high and c.close <= midpoint
            breakout_close = c.close < setup.entry_zone_low

        if not close_confirm and not breakout_close:
            return None

        vol_spike = bool(ltf_ctx.volume_spikes and ltf_ctx.volume_spikes[-1].timestamp == c.timestamp)
        fvg_presence = any(
            setup.entry_zone_low <= fvg.midpoint <= setup.entry_zone_high
            for fvg in ltf_ctx.active_fvgs
        )
        liq_in_zone = any(setup.entry_zone_low <= z.price <= setup.entry_zone_high for z in ltf_ctx.liquidity_zones)
        session = current_session()

        return Trigger(
            setup=setup,
            conditions=TriggerCondition(close_confirm=close_confirm, breakout_close=breakout_close),
            confidence_factors={
                "htf_alignment": True,
                "fvg_presence": fvg_presence,
                "volume_confirmation": vol_spike,
                "liquidity_confluence": liq_in_zone,
                "session_time": session in {"london", "new_york", "overlap"},
            },
            timestamp=c.timestamp,
        )
