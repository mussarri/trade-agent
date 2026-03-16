from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from core.engine import SignalEngine


class ConnectionManager:
    def __init__(self):
        self.connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self.connections.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self.connections.discard(ws)

    async def broadcast_json(self, payload: dict) -> None:
        async with self._lock:
            targets = list(self.connections)
        if not targets:
            return
        await asyncio.gather(
            *(ws.send_json(payload) for ws in targets),
            return_exceptions=True,
        )


def create_app(engine: SignalEngine) -> FastAPI:
    manager = ConnectionManager()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        live_task: asyncio.Task | None = None
        mode = os.getenv("ENGINE_MODE", "demo").lower()
        if mode == "live":
            from config.settings import load_settings
            import logging
            _log = logging.getLogger(__name__)
            cfg, _ = load_settings()
            live_task = asyncio.create_task(
                engine.run_live(exchange_id=cfg.exchange.id, sandbox=cfg.exchange.sandbox)
            )
            live_task.add_done_callback(
                lambda t: _log.error("run_live crashed: %s", t.exception())
                if not t.cancelled() and t.exception() else None
            )
        else:
            await engine.seed_demo_data(bars=200)
        yield
        if live_task is not None:
            live_task.cancel()
            try:
                await live_task
            except (asyncio.CancelledError, Exception):
                pass

    app = FastAPI(title="trade-agent", version="2.0.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.engine = engine
    app.state.ws_manager = manager

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/exchange/status")
    async def exchange_status() -> dict:
        mode = os.getenv("ENGINE_MODE", "demo").lower()
        return {
            "mode": mode,
            "exchange": "binance",
            "symbols": app.state.engine.symbols,
            "htf": [h for h, _ in app.state.engine.tf_pairs],
            "ltf": [l for _, l in app.state.engine.tf_pairs],
            "active_signals": len(app.state.engine.store.active_signals),
            "connected": mode == "live",
        }

    @app.get("/api/signals")
    async def get_signals() -> list[dict]:
        return [s.model_dump(mode="json") for s in app.state.engine.store.active_signals]

    @app.get("/api/signals/history")
    async def get_history() -> list[dict]:
        return [s.model_dump(mode="json") for s in app.state.engine.store.history]

    @app.get("/api/setups")
    async def get_active_setups() -> dict:
        result = {}
        for key, setups in app.state.engine.active_setups.items():
            if setups:
                result[key] = [
                    {
                        "scenario":        s.scenario_name,
                        "symbol":          s.symbol,
                        "direction":       s.direction,
                        "watch_low":       s.entry_zone_low,
                        "watch_high":      s.entry_zone_high,
                        "candles_elapsed": s.candles_elapsed,
                        "timeout_candles": s.max_candles,
                        "progress_pct":    round(s.candles_elapsed / max(s.max_candles, 1) * 100),
                    }
                    for s in setups
                ]
        return result

    @app.get("/api/market/{symbol}")
    async def get_market_context(symbol: str) -> dict:
        """Sembol için HTF + LTF yapısal özet."""
        sym = symbol if "/" in symbol else symbol.replace("USDT", "/USDT")
        htf_tfs = [h for h, _ in app.state.engine.tf_pairs]
        ltf_tfs = [l for _, l in app.state.engine.tf_pairs]
        htf_ctx = next(
            (app.state.engine.contexts.get((sym, h)) for h in htf_tfs),
            None,
        )
        ltf_ctx = next(
            (app.state.engine.contexts.get((sym, l)) for l in ltf_tfs),
            None,
        )
        return {
            "symbol":          sym,
            "htf_trend":       htf_ctx.trend if htf_ctx else "unknown",
            "ltf_trend":       ltf_ctx.trend if ltf_ctx else "unknown",
            "active_fvgs":     len(ltf_ctx.active_fvgs) if ltf_ctx else 0,
            "liquidity_zones": len(ltf_ctx.liquidity_zones) if ltf_ctx else 0,
            "last_bos":        str(ltf_ctx.last_bos) if ltf_ctx and ltf_ctx.last_bos else None,
        }

    @app.get("/api/stats")
    async def get_stats() -> dict:
        store = app.state.engine.store
        base = store.stats()

        scenario_scores: dict[str, list[int]] = {}
        for s in store.history:
            scenario_scores.setdefault(s.scenario_name, []).append(s.score)

        enriched_scenarios = {
            name: {
                "count": base["scenarios"].get(name, 0),
                "avg_score": round(sum(scores) / len(scores), 1),
            }
            for name, scores in scenario_scores.items()
        }

        symbol_detail: dict[str, dict] = {}
        for sym in app.state.engine.symbols:
            active = sum(1 for s in store.active_signals if s.symbol == sym)
            ltf_ctx = next(
                (app.state.engine.contexts.get((sym, l)) for _, l in app.state.engine.tf_pairs),
                None,
            )
            last_structure = ltf_ctx.trend if ltf_ctx else "unknown"
            symbol_detail[sym] = {
                "active": active,
                "last_structure": last_structure,
                "total_signals": base["symbols"].get(sym, 0),
            }

        return {
            "total_signals_today": len(store.history),
            "active_signals": len(store.active_signals),
            "scenarios": enriched_scenarios,
            "symbols": symbol_detail,
        }

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await manager.connect(ws)
        await ws.send_json({
            "type": "snapshot",
            "signals": [s.model_dump(mode="json") for s in app.state.engine.store.active_signals],
        })
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            await manager.disconnect(ws)

    return app
