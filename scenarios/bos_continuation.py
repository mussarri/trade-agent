from __future__ import annotations

from core.models import Setup, Trigger, TriggerCondition
from core.structure import calculate_atr, current_session
from scenarios.base import BaseScenario


class BosContinuationScenario(BaseScenario):
    """BOS sonrası pullback entry — trend devamı ana senaryo.

    detect_setup: LTF BOS oluştu, HTF trend yönünde pullback bölgesi bekle.
    detect_trigger: close_confirm veya sweep_reversal.
    """

    name = "bos_continuation"
    alert_type = "BOS_CONTINUATION"

    def detect_setup(self, htf_ctx, ltf_ctx) -> Setup | None:
        htf_trend = htf_ctx.trend
        if htf_trend == "neutral":
            return None

        # Continuation quality gate: external BOS + displacement required
        ext_bos = ltf_ctx.last_external_bos
        if not ext_bos:
            return None
        if not ext_bos.displacement:
            return None

        ltf_bos_dir = ext_bos.direction  # "bullish" | "bearish"

        if htf_trend == "bullish":
            if ltf_bos_dir != "bullish":
                return None
            direction = "long"
        elif htf_trend == "bearish":
            if ltf_bos_dir != "bearish":
                return None
            direction = "short"
        else:
            return None

        bos_level = ext_bos.level

        # Pullback bölgesi
        if direction == "long":
            swing_low = ltf_ctx.swing_lows[-1].price if ltf_ctx.swing_lows else bos_level * 0.995
            watch_low = swing_low
            watch_high = bos_level
            invalidation = bos_level * (1 - 0.002)  # BOS seviyesi altı kapanış
        else:
            swing_high = ltf_ctx.swing_highs[-1].price if ltf_ctx.swing_highs else bos_level * 1.005
            watch_low = bos_level
            watch_high = swing_high
            invalidation = bos_level * (1 + 0.002)  # BOS seviyesi üstü kapanış

        # FVG aynı bölgede varsa watch zone'u FVG sınırlarına daralt
        has_fvg = False
        for fvg in ltf_ctx.active_fvgs:
            if fvg.direction == direction:
                if fvg.low >= watch_low and fvg.high <= watch_high:
                    watch_low = fvg.low
                    watch_high = fvg.high
                    has_fvg = True
                    break
        # A continuation setup without imbalance context is usually low quality.
        if not has_fvg:
            return None

        if watch_low >= watch_high:
            return None

        current_price = ltf_ctx.last_close
        if current_price and abs(current_price - watch_high) / current_price > 0.02:
            return None

        swing_low_ref = ltf_ctx.swing_lows[-1].price if ltf_ctx.swing_lows else watch_low * 0.99
        swing_high_ref = ltf_ctx.swing_highs[-1].price if ltf_ctx.swing_highs else watch_high * 1.01

        return Setup(
            scenario_name=self.name,
            alert_type=self.alert_type,
            symbol=ltf_ctx.symbol,
            timeframe=ltf_ctx.timeframe,
            direction=direction,
            entry_zone_low=watch_low,
            entry_zone_high=watch_high,
            swing_low=swing_low_ref,
            swing_high=swing_high_ref,
            invalidation_level=invalidation,
            max_candles=20,
            meta={
                "bos_level": bos_level,
                "has_fvg": has_fvg,
                "bos_kind": ext_bos.structure_kind,
            },
        )

    def detect_trigger(self, setup: Setup, ltf_ctx) -> Trigger | None:
        if not ltf_ctx.candles:
            return None
        c = ltf_ctx.candles[-1]
        midpoint = (setup.entry_zone_low + setup.entry_zone_high) / 2

        close_confirm = False
        sweep_reversal = False

        if setup.direction == "long":
            # Option A — close_confirm: close içinde ve üst yarıda
            if setup.entry_zone_low <= c.close <= setup.entry_zone_high and c.close > midpoint:
                close_confirm = True
            # Option B — sweep_reversal: wick dışı + geri kapanış
            elif c.low < setup.entry_zone_low and c.close > setup.entry_zone_low:
                sweep_reversal = True
        else:
            # Option A — close_confirm: close içinde ve alt yarıda
            if setup.entry_zone_low <= c.close <= setup.entry_zone_high and c.close < midpoint:
                close_confirm = True
            # Option B — sweep_reversal: wick dışı + geri kapanış
            elif c.high > setup.entry_zone_high and c.close < setup.entry_zone_high:
                sweep_reversal = True

        if not close_confirm and not sweep_reversal:
            return None

        # Volume confirmation — trigger mumunda spike var mı
        vol_spike = bool(
            ltf_ctx.volume_spikes and ltf_ctx.volume_spikes[-1].timestamp == c.timestamp
        )

        # Liquidity confluence — watch bölgesinde LiquidityZone var mı
        liq_in_zone = any(
            setup.entry_zone_low <= z.price <= setup.entry_zone_high
            for z in ltf_ctx.liquidity_zones
        )

        session = current_session()
        confidence_factors = {
            "htf_alignment":        True,
            "fvg_presence":         setup.meta.get("has_fvg", False),
            "volume_confirmation":  vol_spike,
            "liquidity_confluence": liq_in_zone,
            "session_time":         session in {"london", "new_york", "overlap"},
        }

        return Trigger(
            setup=setup,
            conditions=TriggerCondition(
                close_confirm=close_confirm,
                sweep_reversal=sweep_reversal,
            ),
            confidence_factors=confidence_factors,
            timestamp=c.timestamp,
        )
