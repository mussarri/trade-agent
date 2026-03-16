from __future__ import annotations

import asyncio
import logging
from collections import Counter, defaultdict, deque
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from alerts.base import BaseAlert
from core.context import StructureContext
from core.models import AlertPayload, Setup, Trigger
from core.structure import calculate_atr, current_session
from risk.planner import RiskPlanner
from scenarios import load_all_scenarios
from scoring.scorer import MIN_RR_RATIO, MIN_SCORE, score

logger = logging.getLogger(__name__)


class SignalStore:
    def __init__(self, history_size: int = 50):
        self.active_signals: list[AlertPayload] = []
        self.history: deque[AlertPayload] = deque(maxlen=history_size)

    def add(self, payload: AlertPayload) -> None:
        self.active_signals = [
            s
            for s in self.active_signals
            if not (
                s.symbol == payload.symbol
                and s.timeframe == payload.timeframe
                and s.scenario_name == payload.scenario_name
            )
        ]
        self.active_signals.append(payload)
        self.history.appendleft(payload)

    def update_status(self, signal_id: str, new_status: str) -> AlertPayload | None:
        """Update status of a signal in-place. Returns updated signal or None."""
        closed_statuses = {"tp3_hit", "stopped", "invalidated", "expired"}
        updated: AlertPayload | None = None
        new_active: list[AlertPayload] = []
        for s in self.active_signals:
            if s.id == signal_id:
                s = s.model_copy(update={"status": new_status})
                updated = s
                if new_status not in closed_statuses:
                    new_active.append(s)
            else:
                new_active.append(s)
        self.active_signals = new_active
        # Sync history
        self.history = deque(
            (s.model_copy(update={"status": new_status}) if s.id == signal_id else s
             for s in self.history),
            maxlen=self.history.maxlen,
        )
        return updated

    def stats(self) -> dict[str, dict[str, int]]:
        scenario_counter = Counter(s.scenario_name for s in self.history)
        symbol_counter = Counter(s.symbol for s in self.history)
        return {
            "scenarios": dict(scenario_counter),
            "symbols": dict(symbol_counter),
        }


class Pipeline:
    def __init__(
        self,
        min_score: int = MIN_SCORE,
        min_rr_ratio: float = MIN_RR_RATIO,
        risk_planner: RiskPlanner | None = None,
        alerts: list[BaseAlert] | None = None,
        enabled_scenarios: list[str] | None = None,
        signal_store: SignalStore | None = None,
        broadcaster: Callable[[dict[str, Any]], asyncio.Future | Any] | None = None,
        cooldown_minutes: int = 5,
    ):
        self.min_score = min_score
        self.min_rr_ratio = min_rr_ratio
        self.risk_planner = risk_planner or RiskPlanner()
        self.alerts = alerts or []
        self.scenarios = load_all_scenarios(enabled=enabled_scenarios)
        self.signal_store = signal_store or SignalStore()
        self.broadcaster = broadcaster
        self.cooldown_minutes = cooldown_minutes

        # Two-stage state: "scenario:symbol" → list[Setup]
        self.active_setups: dict[str, list[Setup]] = {}
        # Cooldown: symbol → last alert datetime (per-symbol, not per-scenario)
        self.alert_cooldowns: dict[str, datetime] = {}

    def _setup_key(self, symbol: str, scenario_name: str) -> str:
        return f"{scenario_name}:{symbol}"

    def _is_on_cooldown(self, symbol: str) -> bool:
        last = self.alert_cooldowns.get(symbol)
        if last is None:
            return False
        return datetime.now(timezone.utc) - last < timedelta(minutes=self.cooldown_minutes)

    def _set_cooldown(self, symbol: str) -> None:
        self.alert_cooldowns[symbol] = datetime.now(timezone.utc)

    def _merge_confluence(self, signals: list[AlertPayload]) -> list[AlertPayload]:
        """Aynı sembol + aynı yönde birden fazla sinyal → tek birleşik sinyal."""
        if len(signals) <= 1:
            return signals

        groups: dict[tuple, list[AlertPayload]] = defaultdict(list)
        for s in signals:
            groups[(s.symbol, s.direction)].append(s)

        merged: list[AlertPayload] = []
        for (symbol, direction), group in groups.items():
            if len(group) == 1:
                merged.extend(group)
                continue
            best = max(group, key=lambda s: s.score)
            merged_factors: dict[str, bool] = {}
            for s in group:
                for k, v in s.confidence_factors.items():
                    merged_factors[k] = merged_factors.get(k, False) or v
            best = best.model_copy(update={"confidence_factors": merged_factors})
            logger.info(
                "Confluence merge: %d signals → 1 (%s %s score=%d)",
                len(group), symbol, direction, best.score,
            )
            merged.append(best)

        return merged

    async def run(self, htf_ctx: StructureContext, ltf_ctx: StructureContext) -> list[AlertPayload]:
        symbol = ltf_ctx.symbol

        # ── HARD FILTER ───────────────────────────────────────────────────
        htf_trend = htf_ctx.trend
        if htf_trend == "neutral":
            logger.debug("HTF neutral — %s skipped", symbol)
            return []

        produced: list[AlertPayload] = []

        for scenario in self.scenarios:
            skey = self._setup_key(symbol, scenario.name)
            setups = self.active_setups.get(skey, [])

            # 1. Age candles
            for s in setups:
                s.candles_elapsed += 1

            # 2. Invalidation check
            valid_setups = [s for s in setups if not scenario.is_invalidated(s, ltf_ctx)]
            self.active_setups[skey] = valid_setups

            # 3. New setup — only when no active setup, only if HTF trend matches
            if not valid_setups:
                new_setup = scenario.detect_setup(htf_ctx, ltf_ctx)
                if new_setup:
                    trend_ok = (
                        (htf_trend == "bullish" and new_setup.direction == "long") or
                        (htf_trend == "bearish" and new_setup.direction == "short")
                    )
                    if trend_ok:
                        self.active_setups[skey] = [new_setup]
                        logger.info(
                            "Setup: %s %s %s watch=[%.4f, %.4f]",
                            scenario.name, symbol, new_setup.direction,
                            new_setup.entry_zone_low, new_setup.entry_zone_high,
                        )
                        setup_dict = {
                            "event": "setup",
                            "scenario_name": new_setup.scenario_name,
                            "alert_type": new_setup.alert_type,
                            "symbol": new_setup.symbol,
                            "pair": new_setup.symbol.replace("/", ""),
                            "timeframe": new_setup.timeframe,
                            "timeframe_htf": htf_ctx.timeframe,
                            "direction": new_setup.direction,
                            "htf_trend": htf_trend,
                            "entry_zone_low": new_setup.entry_zone_low,
                            "entry_zone_high": new_setup.entry_zone_high,
                            "invalidation_level": new_setup.invalidation_level,
                            "max_candles": new_setup.max_candles,
                            "meta": new_setup.meta,
                        }
                        await self._dispatch_setup_alerts(setup_dict)
                        if self.broadcaster:
                            msg = {"type": "setup_detected", "data": setup_dict}
                            maybe = self.broadcaster(msg)
                            if asyncio.iscoroutine(maybe):
                                await maybe
                continue

            # 4. Trigger check
            for setup in valid_setups[:]:
                if self._is_on_cooldown(symbol):
                    continue

                trigger = scenario.detect_trigger(setup, ltf_ctx)
                if not trigger:
                    continue

                trigger_dict = {
                    "event": "trigger",
                    "scenario_name": trigger.setup.scenario_name,
                    "alert_type": trigger.setup.alert_type,
                    "symbol": trigger.setup.symbol,
                    "pair": trigger.setup.symbol.replace("/", ""),
                    "timeframe": trigger.setup.timeframe,
                    "timeframe_htf": htf_ctx.timeframe,
                    "direction": trigger.setup.direction,
                    "htf_trend": htf_trend,
                    "entry_zone_low": trigger.setup.entry_zone_low,
                    "entry_zone_high": trigger.setup.entry_zone_high,
                    "invalidation_level": trigger.setup.invalidation_level,
                    "conditions": trigger.conditions.model_dump(),
                    "confidence_factors": trigger.confidence_factors,
                    "timestamp": trigger.timestamp.isoformat(),
                }
                await self._dispatch_trigger_alerts(trigger_dict)
                if self.broadcaster:
                    msg = {"type": "trigger_fired", "data": trigger_dict}
                    maybe = self.broadcaster(msg)
                    if asyncio.iscoroutine(maybe):
                        await maybe

                computed_score = score(trigger)
                if computed_score < self.min_score:
                    logger.debug("Score too low: %d for %s %s", computed_score, symbol, scenario.name)
                    self.active_setups[skey] = [s for s in valid_setups if s is not setup]
                    continue

                try:
                    atr = calculate_atr(ltf_ctx.candles)
                    swing_highs = [s.price for s in ltf_ctx.swing_highs]
                    swing_lows = [s.price for s in ltf_ctx.swing_lows]
                    plan = self.risk_planner.plan_from_trigger(
                        trigger, atr=atr, swing_highs=swing_highs, swing_lows=swing_lows
                    )
                except Exception as exc:
                    logger.warning("RiskPlanner failed: %s", exc)
                    continue

                if plan.rr_ratio < self.min_rr_ratio:
                    logger.debug("R:R too low: %.2f for %s", plan.rr_ratio, symbol)
                    self.active_setups[skey] = [s for s in valid_setups if s is not setup]
                    continue

                sess = current_session()
                payload = AlertPayload(
                    scenario_name=scenario.name,
                    alert_type=scenario.alert_type,
                    symbol=symbol,
                    pair=symbol.replace("/", ""),
                    timeframe=ltf_ctx.timeframe,
                    timeframe_ltf=ltf_ctx.timeframe,
                    timeframe_htf=htf_ctx.timeframe,
                    direction=trigger.setup.direction,
                    score=computed_score,
                    confidence_factors=trigger.confidence_factors,
                    risk_plan=plan,
                    ict_full_setup=trigger.setup.meta.get("ict_bonus", False),
                    htf_trend=htf_trend,
                    session=sess,
                    scenario_detail=scenario.describe(setup, trigger),
                    timestamp=trigger.timestamp,
                )

                self._set_cooldown(symbol)
                self.active_setups[skey] = [s for s in valid_setups if s is not setup]

                logger.info(
                    "Trigger: %s %s %s | score=%d | session=%s",
                    scenario.name, symbol, trigger.setup.direction, computed_score, sess,
                )

                self.signal_store.add(payload)
                produced.append(payload)

                raw = payload.model_dump(mode="json")
                await self._dispatch_alerts(raw)
                if self.broadcaster:
                    msg = {"type": "new_signal", "data": raw}
                    maybe = self.broadcaster(msg)
                    if asyncio.iscoroutine(maybe):
                        await maybe

        await self._check_active_signals(ltf_ctx)
        return self._merge_confluence(produced)

    async def _check_active_signals(self, ltf_ctx: StructureContext) -> None:
        """Check active signals for TP hits, stop loss, and invalidation on each LTF candle."""
        if not ltf_ctx.candles:
            return
        c = ltf_ctx.candles[-1]

        # Only monitor signals belonging to this symbol + LTF timeframe
        candidates = [
            s for s in self.signal_store.active_signals
            if s.symbol == ltf_ctx.symbol and s.timeframe == ltf_ctx.timeframe
        ]

        for signal in candidates:
            rp = signal.risk_plan
            status = signal.status
            new_status: str | None = None

            if signal.direction == "long":
                # Invalidation / stop — highest priority
                if c.low <= rp.stop_loss:
                    new_status = "stopped"
                elif c.low <= rp.invalidation_level:
                    new_status = "invalidated"
                # TP levels — check in sequence
                elif status == "active" and c.high >= rp.tp1:
                    new_status = "tp1_hit"
                elif status == "tp1_hit" and c.high >= rp.tp2:
                    new_status = "tp2_hit"
                elif status == "tp2_hit" and c.high >= rp.tp3:
                    new_status = "tp3_hit"
            else:  # short
                if c.high >= rp.stop_loss:
                    new_status = "stopped"
                elif c.high >= rp.invalidation_level:
                    new_status = "invalidated"
                elif status == "active" and c.low <= rp.tp1:
                    new_status = "tp1_hit"
                elif status == "tp1_hit" and c.low <= rp.tp2:
                    new_status = "tp2_hit"
                elif status == "tp2_hit" and c.low <= rp.tp3:
                    new_status = "tp3_hit"

            if new_status is None:
                continue

            updated = self.signal_store.update_status(signal.id, new_status)
            if updated is None:
                continue

            logger.info(
                "Signal %s: %s %s → %s",
                signal.id[:8], signal.symbol, signal.direction, new_status,
            )

            event_dict = updated.model_dump(mode="json")

            if new_status in ("stopped", "invalidated"):
                await asyncio.gather(
                    *(alert.send_invalidation(event_dict) if new_status == "invalidated"
                      else alert.send_stop_hit(event_dict)
                      for alert in self.alerts),
                    return_exceptions=True,
                )
            elif new_status in ("tp1_hit", "tp2_hit", "tp3_hit"):
                await asyncio.gather(
                    *(alert.send_tp_hit(event_dict) for alert in self.alerts),
                    return_exceptions=True,
                )

            if self.broadcaster:
                msg = {"type": "signal_update", "data": event_dict}
                maybe = self.broadcaster(msg)
                if asyncio.iscoroutine(maybe):
                    await maybe

    async def _dispatch_alerts(self, payload: dict[str, Any]) -> None:
        if not self.alerts:
            return
        await asyncio.gather(*(alert.send(payload) for alert in self.alerts), return_exceptions=True)

    async def _dispatch_setup_alerts(self, payload: dict[str, Any]) -> None:
        if not self.alerts:
            return
        await asyncio.gather(*(alert.send_setup(payload) for alert in self.alerts), return_exceptions=True)

    async def _dispatch_trigger_alerts(self, payload: dict[str, Any]) -> None:
        if not self.alerts:
            return
        await asyncio.gather(*(alert.send_trigger(payload) for alert in self.alerts), return_exceptions=True)
