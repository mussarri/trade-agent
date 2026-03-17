from __future__ import annotations

from core.models import Setup, Trigger, TriggerCondition
from core.structure import calculate_atr, current_session
from scenarios.base import BaseScenario


class LiquiditySweepScenario(BaseScenario):
    """Sweep + structure shift onayı sonrası reversal."""

    name = "liquidity_sweep"
    alert_type = "LIQUIDITY_SWEEP_REVERSAL_CONFIRMED"

    def detect_setup(self, htf_ctx, ltf_ctx) -> Setup | None:
        htf_trend = htf_ctx.trend
        if htf_trend == "neutral":
            return None
        direction = "long" if htf_trend == "bullish" else "short"

        atr = calculate_atr(ltf_ctx.candles) if ltf_ctx.candles else 0.0
        if atr == 0.0:
            return None

        # Sweep must already be printed; setup is a reversal attempt awaiting structure confirmation.
        recent = None
        for ev in reversed(ltf_ctx.recent_sweeps):
            if direction == "long" and ev.direction == "bullish":
                recent = ev
                break
            if direction == "short" and ev.direction == "bearish":
                recent = ev
                break
        if recent is None:
            return None

        zone_level = recent.price

        if direction == "long":
            watch_low = zone_level - atr * 0.5
            watch_high = zone_level + atr * 0.2
            invalidation = zone_level - atr * 1.5
        else:
            watch_low = zone_level - atr * 0.2
            watch_high = zone_level + atr * 0.5
            invalidation = zone_level + atr * 1.5

        current_price = ltf_ctx.last_close
        if current_price and abs(current_price - watch_high) / current_price > 0.02:
            return None

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
                "sweep_timestamp": recent.timestamp.isoformat(),
            },
        )

    def detect_trigger(self, setup: Setup, ltf_ctx) -> Trigger | None:
        """Sweep tek başına entry değildir; MSS/BOS onayı gerekir."""
        if not ltf_ctx.candles:
            return None
        c = ltf_ctx.candles[-1]
        sweep_ts = setup.meta.get("sweep_timestamp")
        if not sweep_ts:
            return None
        last_bos = ltf_ctx.last_bos
        if not last_bos or last_bos.timestamp.isoformat() <= sweep_ts:
            return None
        if setup.direction == "long" and last_bos.direction != "bullish":
            return None
        if setup.direction == "short" and last_bos.direction != "bearish":
            return None

        # CHoCH or external BOS confirmation after sweep
        choch_ok = bool(
            ltf_ctx.last_choch
            and ltf_ctx.last_choch.timestamp.isoformat() > sweep_ts
            and ((setup.direction == "long" and ltf_ctx.last_choch.direction == "bullish")
                 or (setup.direction == "short" and ltf_ctx.last_choch.direction == "bearish"))
        )
        ext_bos = ltf_ctx.last_external_bos
        ext_bos_ok = bool(
            ext_bos
            and ext_bos.timestamp.isoformat() > sweep_ts
            and ((setup.direction == "long" and ext_bos.direction == "bullish")
                 or (setup.direction == "short" and ext_bos.direction == "bearish"))
        )
        if not (choch_ok or ext_bos_ok):
            return None

        vol_spike = bool(ltf_ctx.volume_spikes and ltf_ctx.volume_spikes[-1].timestamp == c.timestamp)
        zone_level = float(setup.meta.get("zone_level", 0.0))
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
            "fvg_presence":         fvg_near_zone,
            "volume_confirmation":  vol_spike,
            "liquidity_confluence": multi_zone,
            "session_time":         session in {"london", "new_york", "overlap"},
        }

        return Trigger(
            setup=setup,
            conditions=TriggerCondition(sweep_reversal=True, breakout_close=True),
            confidence_factors=confidence_factors,
            timestamp=c.timestamp,
        )
