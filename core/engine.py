from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone

try:
    import ccxt.async_support as ccxt
    import ccxt.pro as ccxtpro
except Exception:
    ccxt = None
    ccxtpro = None


logger = logging.getLogger(__name__)

from alerts.base import BaseAlert
from core.candle import Candle
from core.context import StructureContext
from core.data_feed import DataFeed, FixtureFeed
from core.pipeline import Pipeline, SignalStore
from risk.planner import RiskPlanner

SYMBOL_BASE_PRICES = {
    "BTC/USDT": 83000.0,
    "BTC/USDT:USDT": 83000.0,
    "ETH/USDT": 1900.0,
    "ETH/USDT:USDT": 1900.0,
    "SOL/USDT": 130.0,
    "SOL/USDT:USDT": 130.0,
    "XRP/USDT": 2.2,
    "XRP/USDT:USDT": 2.2,
    "BNB/USDT": 580.0,
    "BNB/USDT:USDT": 580.0,
    "AVAX/USDT": 22.0,
    "AVAX/USDT:USDT": 22.0,
    "XAU/USD": 3300.0,
    "EUR/USD": 1.08,
    "GBP/USD": 1.27,
    "USD/JPY": 155.0,
}
DEFAULT_BASE = 100.0

_TF_UNIT_MINUTES = {"m": 1, "h": 60, "d": 1440, "w": 10080}


def _tf_minutes(tf: str) -> int:
    return int(tf[:-1]) * _TF_UNIT_MINUTES[tf[-1]]


class SignalEngine:
    def __init__(
        self,
        symbols: list[str],
        htf: list[str],
        ltf: list[str],
        min_score: int,
        min_rr_ratio: float,
        risk_per_trade_pct: float,
        atr_sl_multiplier: float,
        enabled_scenarios: list[str],
        alerts: list[BaseAlert] | None = None,
        broadcaster=None,
        htf_pivot_length: int = 5,
        ltf_pivot_length: int = 3,
        min_swing_distance_atr_mult: float = 0.8,
        equal_level_tolerance: float = 0.001,
        use_close_for_break_confirmation: bool = True,
        symbol_tf_groups: list[dict] | None = None,
    ):
        self.symbols = symbols
        # Paired combinations: htf[i] × ltf[i]  e.g. [(1h,5m), (4h,15m)]
        self.tf_pairs: list[tuple[str, str]] = list(zip(htf, ltf))
        self.contexts: dict[tuple[str, str], StructureContext] = {}
        self.store = SignalStore(history_size=50)
        self.structure_context_kwargs = {
            "lookback": max(1, int(ltf_pivot_length)),
            "external_lookback": max(1, int(htf_pivot_length)),
            "ltf_pivot_length": max(1, int(ltf_pivot_length)),
            "htf_pivot_length": max(1, int(htf_pivot_length)),
            "min_swing_distance_atr_mult": max(0.0, float(min_swing_distance_atr_mult)),
            "equal_level_tolerance": max(0.0, float(equal_level_tolerance)),
            "use_close_for_break_confirmation": bool(use_close_for_break_confirmation),
        }

        risk_planner = RiskPlanner(
            risk_per_trade_pct=risk_per_trade_pct,
            atr_sl_multiplier=atr_sl_multiplier,
        )

        self.pipelines: dict[tuple[str, str], Pipeline] = {
            (h, l): Pipeline(
                min_score=min_score,
                min_rr_ratio=min_rr_ratio,
                risk_planner=risk_planner,
                alerts=alerts,
                enabled_scenarios=enabled_scenarios,
                signal_store=self.store,
                broadcaster=broadcaster,
            )
            for h, l in self.tf_pairs
        }

        # Symbol-scoped routing: each pipeline only handles its designated symbols.
        # None means "no restriction" (all symbols allowed) — preserves backward compat.
        self._pipeline_symbol_scope: dict[tuple[str, str], frozenset[str] | None] = {}
        if symbol_tf_groups is not None:
            for group in symbol_tf_groups:
                pair = (group["htf"], group["ltf"])
                syms = frozenset(group["symbols"])
                existing = self._pipeline_symbol_scope.get(pair)
                if existing is None and pair in self._pipeline_symbol_scope:
                    # Was explicitly set to None (all symbols), keep it unrestricted.
                    pass
                else:
                    self._pipeline_symbol_scope[pair] = (
                        existing | syms if existing is not None else syms
                    )
        else:
            for pair in self.tf_pairs:
                self._pipeline_symbol_scope[pair] = None

    def set_broadcaster(self, broadcaster) -> None:
        for pipeline in self.pipelines.values():
            pipeline.broadcaster = broadcaster

    @property
    def active_setups(self) -> dict[str, list]:
        """Merge active_setups from all pipelines for the API."""
        merged: dict[str, list] = {}
        for pipeline in self.pipelines.values():
            for key, setups in pipeline.active_setups.items():
                if setups:
                    merged.setdefault(key, []).extend(setups)
        return merged

    def seed_context(self, ctx: StructureContext) -> None:
        """History yüklendikten sonra engine.contexts'i hemen seed'le (pipeline çalıştırmadan)."""
        self.contexts[(ctx.symbol, ctx.timeframe)] = ctx
        logger.debug(
            "Context seeded: %s %s  candles=%d swings_h=%d swings_l=%d",
            ctx.symbol, ctx.timeframe, len(ctx.candles),
            len(ctx.swing_highs), len(ctx.swing_lows),
        )

    async def on_candle_closed(self, ctx: StructureContext, candle: Candle) -> None:
        self.contexts[(ctx.symbol, ctx.timeframe)] = ctx
        for (h, l), pipeline in self.pipelines.items():
            scope = self._pipeline_symbol_scope.get((h, l))
            if scope is not None and ctx.symbol not in scope:
                continue
            if ctx.timeframe == h:
                await pipeline.dispatch_htf_structure_alerts(ctx)
            if ctx.timeframe == l:
                htf_ctx = self.contexts.get((ctx.symbol, h))
                if htf_ctx:
                    await pipeline.run(htf_ctx, ctx)

    async def run_fixture(self, candles: Iterable[Candle], symbol: str, timeframe: str) -> None:
        ltf_set = {l for _, l in self.tf_pairs}
        feed = FixtureFeed(
            symbol=symbol,
            timeframe=timeframe,
            candles=list(candles),
            on_candle_closed=self.on_candle_closed,
            context_kwargs=self.structure_context_kwargs,
            is_ltf=timeframe in ltf_set,
        )
        await feed.run(delay=0.0)

    async def seed_demo_data(self, bars: int = 200) -> None:
        now = datetime.now(tz=timezone.utc)
        seeded: set[tuple[str, str]] = set()
        for symbol in self.symbols:
            base = SYMBOL_BASE_PRICES.get(symbol, DEFAULT_BASE)
            for h, l in self.tf_pairs:
                scope = self._pipeline_symbol_scope.get((h, l))
                if scope is not None and symbol not in scope:
                    continue
                for tf in dict.fromkeys([h, l]):  # preserves order, deduplicates h==l
                    if (symbol, tf) in seeded:
                        continue
                    seeded.add((symbol, tf))
                    tf_mins = _tf_minutes(tf)
                    candles = self._make_synthetic_candles(
                        symbol=symbol,
                        timeframe=tf,
                        start=now - timedelta(minutes=bars * tf_mins),
                        bars=bars,
                        step_minutes=tf_mins,
                        base=base,
                    )
                    await self.run_fixture(candles, symbol, tf)

    async def run_live(
        self,
        exchange_id: str = "binance",
        sandbox: bool = False,
        market_type: str = "future",
        symbols: list[str] | None = None,
        tf_pairs: list[tuple[str, str]] | None = None,
    ) -> None:
        if ccxtpro is None:
            raise RuntimeError("ccxt[pro] is not installed — pip install ccxt[pro]")

        exchange_cls = getattr(ccxtpro, exchange_id)
        market_type = market_type.lower().strip()
        if market_type not in {"spot", "future", "swap"}:
            raise ValueError(f"Unsupported market_type: {market_type}")

        exchange = exchange_cls({
            "enableRateLimit": True,
            "options": {"defaultType": market_type},
        })
        if sandbox:
            exchange.set_sandbox_mode(True)

        target_symbols = symbols if symbols is not None else self.symbols
        target_pairs = tf_pairs if tf_pairs is not None else self.tf_pairs
        all_tfs = {tf for pair in target_pairs for tf in pair}
        ltf_set = {l for _, l in target_pairs}
        try:
            tasks = []
            for symbol in target_symbols:
                for tf in all_tfs:
                    tasks.append(asyncio.create_task(
                        DataFeed(
                            symbol, tf, exchange,
                            self.on_candle_closed,
                            on_history_ready=self.seed_context,
                            context_kwargs=self.structure_context_kwargs,
                            is_ltf=tf in ltf_set,
                        ).start()
                    ))
            await asyncio.gather(*tasks)
        finally:
            await exchange.close()

    async def run_live_twelvedata(
        self,
        api_key: str,
        symbols: list[str],
        timeframe: str = "1h",
    ) -> None:
        """Start Twelve Data REST polling feeds for the given symbols."""
        from feeds.twelve_data_feed import TwelveDataFeed

        ltf_set = {l for _, l in self.tf_pairs}
        tasks = [
            asyncio.create_task(
                TwelveDataFeed(
                    symbol=symbol,
                    interval=timeframe,
                    api_key=api_key,
                    on_candle_closed=self.on_candle_closed,
                    on_history_ready=self.seed_context,
                    context_kwargs=self.structure_context_kwargs,
                    is_ltf=timeframe in ltf_set,
                ).start()
            )
            for symbol in symbols
        ]
        await asyncio.gather(*tasks)

    def _make_synthetic_candles(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        bars: int,
        step_minutes: int,
        base: float = 50000.0,
    ) -> list[Candle]:
        out: list[Candle] = []
        price = base
        vol_pct = max(0.003, min(0.015, 5.0 / math.sqrt(base)))

        for i in range(bars):
            trend = math.sin(i / 40 * 2 * math.pi) * base * 0.012
            noise = math.sin(i / 5 * 2 * math.pi) * base * vol_pct
            spike = base * vol_pct * 2.5 if (i % 15 == 0) else 0.0
            drift = trend + noise + spike

            o = price
            c = max(base * 0.1, o + drift)
            wick = base * vol_pct * 0.8
            h = max(o, c) + wick * (1 + (i % 3) * 0.2)
            l = min(o, c) - wick * (1 + (i % 4) * 0.15)

            vol_base = 100 + (i % 7) * 15
            volume = vol_base * 3.0 if abs(drift) > base * vol_pct * 1.8 else float(vol_base)

            ts = start + timedelta(minutes=i * step_minutes)
            out.append(Candle(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=ts,
                open=round(o, 4),
                high=round(h, 4),
                low=round(l, 4),
                close=round(c, 4),
                volume=round(volume, 2),
                is_closed=True,
            ))
            price = c
        return out
