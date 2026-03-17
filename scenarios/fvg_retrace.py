from __future__ import annotations

from core.models import Setup, Trigger, TriggerCondition
from core.structure import calculate_atr, current_session
from scenarios.base import BaseScenario


class FvgRetraceScenario(BaseScenario):
    """Displacement + FVG + retrace — smart money entry.

    detect_setup: HTF trend yönünde FVG var, displacement teyidi.
    detect_trigger: close_confirm veya sweep_reversal.
    ICT Full Setup: sweep + displacement + FVG → +15 bonus.
    """

    name = "fvg_retrace"
    alert_type = "SMART_MONEY_ENTRY"

    def detect_setup(self, htf_ctx, ltf_ctx) -> Setup | None:
        htf_trend = htf_ctx.trend
        if htf_trend == "neutral":
            return None
        direction = "long" if htf_trend == "bullish" else "short"

        # HTF trend yönüyle aynı aktif FVG
        matching_fvg = None
        for fvg in ltf_ctx.active_fvgs:
            if fvg.direction == direction:
                matching_fvg = fvg
                break
        if matching_fvg is None:
            return None

        atr = calculate_atr(ltf_ctx.candles) if ltf_ctx.candles else 0.0

        # Displacement kontrolü: body > ATR * 1.5 VEYA volume spike
        has_displacement = False
        if ltf_ctx.candles and len(ltf_ctx.candles) >= 3:
            # FVG'nin displacement mumu = ortadaki mum
            disp_candle = ltf_ctx.candles[-2]
            body = abs(disp_candle.close - disp_candle.open)
            if atr > 0 and body >= atr * 1.5:
                has_displacement = True
            elif ltf_ctx.volume_spikes and ltf_ctx.volume_spikes[-1].timestamp == disp_candle.timestamp:
                has_displacement = True

        if not has_displacement:
            return None

        # invalidation
        if direction == "long":
            invalidation = matching_fvg.low - atr * 0.3
        else:
            invalidation = matching_fvg.high + atr * 0.3

        current_price = ltf_ctx.last_close
        if current_price and abs(current_price - matching_fvg.high) / current_price > 0.02:
            return None

        swing_low = ltf_ctx.swing_lows[-1].price if ltf_ctx.swing_lows else matching_fvg.low * 0.99
        swing_high = ltf_ctx.swing_highs[-1].price if ltf_ctx.swing_highs else matching_fvg.high * 1.01

        return Setup(
            scenario_name=self.name,
            alert_type=self.alert_type,
            symbol=ltf_ctx.symbol,
            timeframe=ltf_ctx.timeframe,
            direction=direction,
            entry_zone_low=matching_fvg.low,
            entry_zone_high=matching_fvg.high,
            swing_low=swing_low,
            swing_high=swing_high,
            invalidation_level=invalidation,
            max_candles=15,
            meta={
                "fvg_midpoint": matching_fvg.midpoint,
                "has_displacement": has_displacement,
                "zone_touched": False,
            },
        )

    def detect_trigger(self, setup: Setup, ltf_ctx) -> Trigger | None:
        if not ltf_ctx.candles:
            return None
        c = ltf_ctx.candles[-1]
        prev = ltf_ctx.candles[-2] if len(ltf_ctx.candles) >= 2 else None

        close_confirm = False
        sweep_reversal = False
        fvg_mid = (setup.entry_zone_high + setup.entry_zone_low) / 2
        zone_width = max(setup.entry_zone_high - setup.entry_zone_low, 1e-9)

        if setup.direction == "long":
            # First-touch transition: outside above -> inside with >=50% retrace depth.
            was_outside = bool(prev and prev.close > setup.entry_zone_high)
            depth = max(0.0, min(1.0, (setup.entry_zone_high - c.low) / zone_width))
            if was_outside and setup.entry_zone_low <= c.close <= setup.entry_zone_high and depth >= 0.5 and c.close >= fvg_mid:
                close_confirm = True
            if c.low < setup.entry_zone_low and c.close > fvg_mid and c.close > c.open:
                sweep_reversal = True
                close_confirm = False
        else:
            was_outside = bool(prev and prev.close < setup.entry_zone_low)
            depth = max(0.0, min(1.0, (c.high - setup.entry_zone_low) / zone_width))
            if was_outside and setup.entry_zone_low <= c.close <= setup.entry_zone_high and depth >= 0.5 and c.close <= fvg_mid:
                close_confirm = True
            if c.high > setup.entry_zone_high and c.close < fvg_mid and c.close < c.open:
                sweep_reversal = True
                close_confirm = False

        if not close_confirm and not sweep_reversal:
            return None

        # ICT Full Setup: swept zone + displacement + FVG birlikte
        swept_zone_exists = any(z.swept for z in ltf_ctx.liquidity_zones)
        ict_bonus = swept_zone_exists and setup.meta.get("has_displacement", False)

        # Volume confirmation — displacement mumunda spike var mı
        vol_confirm = bool(ltf_ctx.volume_spikes) and setup.meta.get("has_displacement", False)

        # Liquidity confluence — FVG öncesinde swept LiquidityZone
        swept_liq = any(z.swept for z in ltf_ctx.liquidity_zones)

        session = current_session()
        confidence_factors = {
            "htf_alignment":        True,
            "fvg_presence":         True,
            "volume_confirmation":  vol_confirm,
            "liquidity_confluence": swept_liq,
            "session_time":         session in {"london", "new_york", "overlap"},
        }

        # ICT bonus → setup.meta'ya yaz
        trigger_meta = dict(setup.meta)
        trigger_meta["ict_bonus"] = ict_bonus
        updated_setup = setup.model_copy(update={"meta": trigger_meta})

        return Trigger(
            setup=updated_setup,
            conditions=TriggerCondition(
                close_confirm=close_confirm,
                sweep_reversal=sweep_reversal,
            ),
            confidence_factors=confidence_factors,
            timestamp=c.timestamp,
        )
