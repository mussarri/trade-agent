from __future__ import annotations

from core.models import RiskPlan, Setup, Trigger
from scenarios.base import ScenarioMatch


class RiskPlanner:
    def __init__(self, risk_per_trade_pct: float = 1.0, atr_sl_multiplier: float = 0.5):
        self.risk_per_trade_pct = risk_per_trade_pct
        self.atr_sl_multiplier = atr_sl_multiplier

    def plan(self, match: ScenarioMatch, atr: float = 1.0) -> RiskPlan:
        entry_low = match.key_levels.get("entry_zone_low")
        entry_high = match.key_levels.get("entry_zone_high")
        if entry_low is None or entry_high is None:
            raise ValueError("Scenario match must include entry_zone_low and entry_zone_high")

        swing_low = match.key_levels.get("swing_low", entry_low)
        swing_high = match.key_levels.get("swing_high", entry_high)
        return self._build_plan(match.direction, entry_low, entry_high, swing_low, swing_high, atr)

    def plan_from_trigger(
        self,
        trigger: Trigger,
        atr: float = 0.0,
        swing_highs: list[float] | None = None,
        swing_lows: list[float] | None = None,
    ) -> RiskPlan:
        setup = trigger.setup
        return self._build_plan(
            setup.direction,
            setup.entry_zone_low,
            setup.entry_zone_high,
            setup.swing_low,
            setup.swing_high,
            atr,
            liquidity_above=swing_highs,
            liquidity_below=swing_lows,
            entry_override=float(setup.meta.get("entry_price")) if setup.meta.get("entry_price") is not None else None,
        )

    def _build_plan(
        self,
        direction: str,
        entry_low: float,
        entry_high: float,
        swing_low: float,
        swing_high: float,
        atr: float,
        liquidity_above: list[float] | None = None,
        liquidity_below: list[float] | None = None,
        entry_override: float | None = None,
    ) -> RiskPlan:
        entry_mid = entry_override if entry_override is not None else (entry_low + entry_high) / 2

        if direction == "long":
            stop_loss = swing_low
            risk = max(entry_mid - stop_loss, 1e-9)
            # Use structural swing highs as liquidity targets; fall back to R-multiples.
            levels = sorted(p for p in (liquidity_above or []) if p > entry_mid)
            tp1 = levels[0] if len(levels) >= 1 else entry_mid + risk * 2.0
            tp2 = levels[1] if len(levels) >= 2 else entry_mid + risk * 3.0
            extension = max(swing_high - swing_low, risk)
            tp3 = max(entry_mid + extension * 1.272, tp2)
            rr = (tp1 - entry_mid) / risk
            invalidation = swing_low
        else:
            stop_loss = swing_high
            risk = max(stop_loss - entry_mid, 1e-9)
            # Use structural swing lows as liquidity targets; fall back to R-multiples.
            levels = sorted((p for p in (liquidity_below or []) if p < entry_mid), reverse=True)
            tp1 = levels[0] if len(levels) >= 1 else entry_mid - risk * 2.0
            tp2 = levels[1] if len(levels) >= 2 else entry_mid - risk * 3.0
            extension = max(swing_high - swing_low, risk)
            tp3 = min(entry_mid - extension * 1.272, tp2)
            rr = (entry_mid - tp1) / risk
            invalidation = swing_high

        return RiskPlan(
            entry_low=entry_low,
            entry_high=entry_high,
            stop_loss=stop_loss,
            tp1=tp1,
            tp2=tp2,
            tp3=tp3,
            rr_ratio=rr,
            position_size_pct=self.risk_per_trade_pct,
            invalidation_level=invalidation,
        )
