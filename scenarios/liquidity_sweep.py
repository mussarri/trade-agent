from __future__ import annotations

from core.models import Setup, Trigger, TriggerCondition
from core.structure import calculate_atr, current_session
from scenarios.base import BaseScenario


class LiquiditySweepScenario(BaseScenario):
    """Stop hunt → trend yönüne dönüş.

    HTF bullish → equal LOW sweep ara (buy-side entry).
    HTF bearish → equal HIGH sweep ara (sell-side entry).
    Sweep olmadan trigger yok — close_confirm kabul edilmez.
    """

    name = "liquidity_sweep"
    alert_type = "LIQUIDITY_SWEEP"

    def detect_setup(self, htf_ctx, ltf_ctx) -> Setup | None:
        htf_trend = htf_ctx.trend
        direction = "long" if htf_trend == "bullish" else "short"

        atr = calculate_atr(ltf_ctx.candles) if ltf_ctx.candles else 0.0
        if atr == 0.0:
            return None

        # Zone yönü HTF trend ile uyumlu: bullish → equal_low, bearish → equal_high
        target_kind = "low" if direction == "long" else "high"
        candidate = None
        for z in ltf_ctx.liquidity_zones:
            if not z.swept and z.kind == target_kind:
                candidate = z
                break

        if candidate is None:
            return None

        zone_level = candidate.price

        if direction == "long":
            watch_low = zone_level - atr * 0.5
            watch_high = zone_level + atr * 0.2
            invalidation = zone_level - atr * 1.5
        else:
            watch_low = zone_level - atr * 0.2
            watch_high = zone_level + atr * 0.5
            invalidation = zone_level + atr * 1.5

        swing_low = ltf_ctx.swing_lows[-1].price if ltf_ctx.swing_lows else watch_low * 0.99
        swing_high = ltf_ctx.swing_highs[-1].price if ltf_ctx.swing_highs else watch_high * 1.01

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
            max_candles=30,
            meta={
                "zone_level": zone_level,
                "zone_kind": target_kind,
            },
        )

    def detect_trigger(self, setup: Setup, ltf_ctx) -> Trigger | None:
        """SWEEP OLMADAN TRİGGER YOK — close_confirm kabul edilmez."""
        if not ltf_ctx.candles:
            return None
        c = ltf_ctx.candles[-1]
        zone_level = setup.meta.get("zone_level")
        if zone_level is None:
            return None

        sweep_reversal = False
        if setup.direction == "long":
            # Equal low sweep: wick below zone, close above
            if c.low < zone_level and c.close > zone_level:
                sweep_reversal = True
        else:
            # Equal high sweep: wick above zone, close below
            if c.high > zone_level and c.close < zone_level:
                sweep_reversal = True

        if not sweep_reversal:
            return None

        # Volume confirmation — sweep mumunda spike var mı
        vol_spike = bool(ltf_ctx.volume_spikes and ltf_ctx.volume_spikes[-1].timestamp == c.timestamp)

        # FVG veya OB sweep bölgesinde
        fvg_near_zone = any(
            abs(fvg.midpoint - zone_level) / max(zone_level, 1e-9) < 0.01
            for fvg in ltf_ctx.active_fvgs
        )

        # Birden fazla equal level aynı bölgede
        multi_zone = sum(
            1 for z in ltf_ctx.liquidity_zones
            if abs(z.price - zone_level) / max(zone_level, 1e-9) < 0.005
        ) >= 2

        session = current_session()
        confidence_factors = {
            "htf_alignment":        True,
            "fvg_or_ob_presence":   fvg_near_zone,
            "volume_confirmation":  vol_spike,
            "liquidity_confluence": multi_zone,
            "session_time":         session in {"london", "new_york", "overlap"},
        }

        return Trigger(
            setup=setup,
            conditions=TriggerCondition(sweep_reversal=True),
            confidence_factors=confidence_factors,
            timestamp=c.timestamp,
        )
