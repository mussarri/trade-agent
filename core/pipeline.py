from __future__ import annotations

import asyncio
import logging
from collections import Counter, deque
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from alerts.base import BaseAlert
from core.context import StructureContext
from core.models import AlertPayload, Setup
from core.structure import current_session
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

        self.active_setups: dict[str, list[Setup]] = {}
        self.cooldown_minutes = cooldown_minutes
        self.alert_cooldowns: dict[tuple, datetime] = {}
        self.setup_registry: dict[str, datetime] = {}
        self.entry_registry: dict[str, datetime] = {}

    def _setup_key(self, symbol: str, scenario_name: str) -> str:
        return f"{scenario_name}:{symbol}"

    def _is_on_cooldown(self, symbol: str, scenario_name: str, timeframe: str, direction: str) -> bool:
        key = (symbol, scenario_name, timeframe, direction)
        last = self.alert_cooldowns.get(key)
        if last is None:
            return False
        return datetime.now(timezone.utc) - last < timedelta(minutes=self.cooldown_minutes)

    def _set_cooldown(self, symbol: str, scenario_name: str, timeframe: str, direction: str) -> None:
        self.alert_cooldowns[(symbol, scenario_name, timeframe, direction)] = datetime.now(timezone.utc)

    def _prune_registries(self, ttl_hours: int = 8) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=ttl_hours)
        self.setup_registry = {k: v for k, v in self.setup_registry.items() if v > cutoff}
        self.entry_registry = {k: v for k, v in self.entry_registry.items() if v > cutoff}

    async def run(self, htf_ctx: StructureContext, ltf_ctx: StructureContext) -> list[AlertPayload]:
        produced: list[AlertPayload] = []
        symbol = ltf_ctx.symbol
        self._prune_registries()

        for scenario in self.scenarios:
            key = self._setup_key(symbol, scenario.name)
            setups = self.active_setups.setdefault(key, [])

            for s in setups:
                s.candles_elapsed += 1

            valid_setups: list[Setup] = []
            for s in setups:
                if scenario.is_invalidated(s, ltf_ctx):
                    s.state = "EXPIRED"
                    s.meta["state"] = "EXPIRED"
                else:
                    valid_setups.append(s)
            self.active_setups[key] = valid_setups

            new_setup = scenario.detect_setup(htf_ctx, ltf_ctx)
            if new_setup:
                trend = str(new_setup.meta.get("trend", htf_ctx.trend))
                zone_id = str(new_setup.meta.get("zone_id", f"{new_setup.entry_zone_low}:{new_setup.entry_zone_high}"))
                setup_id = str(new_setup.meta.get("setup_id", f"{symbol}:{zone_id}:{trend}"))
                new_setup.meta["zone_id"] = zone_id
                new_setup.meta["setup_id"] = setup_id

                already_active = any(s.meta.get("setup_id") == setup_id for s in self.active_setups[key])
                if setup_id not in self.setup_registry and not already_active:
                    new_setup.state = "ACTIVE"
                    new_setup.meta["state"] = "ACTIVE"
                    self.active_setups[key].append(new_setup)
                    self.setup_registry[setup_id] = datetime.now(timezone.utc)
                    setup_payload = {
                        "type": "SETUP_DETECTED",
                        "scenario_name": new_setup.scenario_name,
                        "alert_type": "SETUP_DETECTED",
                        "status": "active",
                        "symbol": symbol,
                        "trend": trend,
                        "zone": [new_setup.entry_zone_low, new_setup.entry_zone_high],
                        "entry": (new_setup.entry_zone_low + new_setup.entry_zone_high) / 2,
                        "sl": new_setup.invalidation_level,
                        "tp": [],
                        "confidence": 0.55,
                        "setup_id": setup_id,
                        "zone_id": zone_id,
                        "timeframe": new_setup.timeframe,
                        "timeframe_ltf": ltf_ctx.timeframe,
                        "timeframe_htf": htf_ctx.timeframe,
                        "direction": new_setup.direction,
                        "pair": symbol.replace("/", ""),
                        "entry_zone_low": new_setup.entry_zone_low,
                        "entry_zone_high": new_setup.entry_zone_high,
                        "invalidation_level": new_setup.invalidation_level,
                        "max_candles": new_setup.max_candles,
                        "htf_trend": trend,
                        "confidence_factors": {
                            "htf_alignment": True,
                            "pullback_active": True,
                            "zone_reaction": True,
                            "displacement": bool(new_setup.meta.get("displacement_idx") is not None),
                            "micro_bos": True,
                            "first_pullback": True,
                        },
                        "score": 55,
                        "session": current_session(),
                        "scenario_detail": f"{new_setup.scenario_name} | {new_setup.direction} | setup",
                        "timestamp": ltf_ctx.candles[-1].timestamp.isoformat() if ltf_ctx.candles else datetime.now(timezone.utc).isoformat(),
                    }
                    await self._dispatch_setup_alerts(setup_payload)
                    if self.broadcaster:
                        maybe = self.broadcaster({"type": "new_signal", "data": setup_payload})
                        if asyncio.iscoroutine(maybe):
                            await maybe

            for setup in self.active_setups[key][:]:
                setup_id = str(setup.meta.get("setup_id", ""))
                if setup_id and setup_id in self.entry_registry:
                    continue

                trigger = scenario.detect_trigger(setup, ltf_ctx)
                if not trigger:
                    continue

                computed_score = score(trigger)

                swing_highs = [x.price for x in ltf_ctx.swing_highs[-10:]]
                swing_lows = [x.price for x in ltf_ctx.swing_lows[-10:]]
                plan = self.risk_planner.plan_from_trigger(
                    trigger,
                    0.0,
                    swing_highs=swing_highs,
                    swing_lows=swing_lows,
                )
                if plan.rr_ratio < self.min_rr_ratio:
                    continue

                trend = str(setup.meta.get("trend", htf_ctx.trend))
                zone_id = str(setup.meta.get("zone_id", ""))
                setup_id = str(setup.meta.get("setup_id", ""))
                entry_price = float(setup.meta.get("entry_price", (plan.entry_low + plan.entry_high) / 2))

                payload = AlertPayload(
                    type="ENTRY_CONFIRMED",
                    scenario_name=setup.scenario_name,
                    alert_type="ENTRY_CONFIRMED",
                    symbol=symbol,
                    pair=symbol.replace("/", ""),
                    timeframe=ltf_ctx.timeframe,
                    timeframe_ltf=ltf_ctx.timeframe,
                    timeframe_htf=htf_ctx.timeframe,
                    direction=setup.direction,
                    score=computed_score,
                    confidence_factors=trigger.confidence_factors,
                    risk_plan=plan,
                    ict_full_setup=False,
                    scenario_detail=f"{setup.scenario_name} | {setup.direction} | confirmed",
                    htf_trend=trend,
                    trend=trend if trend in {"bullish", "bearish"} else "neutral",
                    session=current_session(),
                    zone=[setup.entry_zone_low, setup.entry_zone_high],
                    entry=entry_price,
                    sl=plan.stop_loss,
                    tp=[plan.tp1, plan.tp2, plan.tp3],
                    confidence=round(computed_score / 100.0, 2),
                    setup_id=setup_id,
                    zone_id=zone_id,
                    timestamp=trigger.timestamp,
                )

                setup.state = "TRIGGERED"
                setup.meta["state"] = "TRIGGERED"
                self.entry_registry[setup_id] = datetime.now(timezone.utc)
                self.active_setups[key].remove(setup)
                produced.append(payload)
                self.signal_store.add(payload)

                payload_dict = payload.model_dump(mode="json")
                await self._dispatch_entry_alerts(payload_dict)
                if self.broadcaster:
                    maybe = self.broadcaster({"type": "new_signal", "data": payload_dict})
                    if asyncio.iscoroutine(maybe):
                        await maybe

        return produced

    async def _dispatch_setup_alerts(self, payload: dict[str, Any]) -> None:
        if not self.alerts:
            return
        await asyncio.gather(*(alert.send_setup(payload) for alert in self.alerts), return_exceptions=True)

    async def _dispatch_entry_alerts(self, payload: dict[str, Any]) -> None:
        if not self.alerts:
            return
        await asyncio.gather(*(alert.send(payload) for alert in self.alerts), return_exceptions=True)
