# core/data_feed.py
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable

try:
    import ccxt.async_support as ccxt
    import ccxt.pro as ccxtpro
except Exception:
    ccxt = None
    ccxtpro = None

from core.candle import Candle
from core.context import StructureContext

logger = logging.getLogger(__name__)

OnCandleClosed = Callable[[StructureContext, Candle], Awaitable[None]]
OnHistoryReady = Callable[[StructureContext], None]

TIMEFRAME_MS = {
    "1m":   60_000,
    "5m":   300_000,
    "15m":  900_000,
    "1h":   3_600_000,
    "4h":   14_400_000,
    "1d":   86_400_000,
}


class DataFeed:
    def __init__(
        self,
        symbol: str,
        timeframe: str,
        exchange,
        on_candle_closed: OnCandleClosed,
        on_history_ready: OnHistoryReady | None = None,
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.exchange = exchange
        self.context = StructureContext(symbol=symbol, timeframe=timeframe)
        self._on_candle_closed = on_candle_closed
        self._on_history_ready = on_history_ready
        self._last_ts: int | None = None   # kapanan son mumun timestamp (ms)

    async def start(self, history_limit: int = 200) -> None:
        await self._load_history(history_limit)
        await self._stream_ws()

    # ── Geçmiş mumları REST ile yükle ────────────────────────────────────
    async def _load_history(self, limit: int) -> None:
        try:
            candles = await self.exchange.fetch_ohlcv(
                self.symbol, timeframe=self.timeframe, limit=limit
            )
            for raw in candles[:-1]:   # son mum henüz kapanmadı, atla
                candle = self._parse(raw, is_closed=True)
                self.context.update(candle)
            if candles:
                self._last_ts = int(candles[-2][0]) if len(candles) >= 2 else None
            logger.info(
                "History loaded: %s %s  bars=%d",
                self.symbol, self.timeframe, len(candles) - 1,
            )
            # engine.contexts'i hemen seed'le — ilk WS tick'ini bekleme
            if self._on_history_ready is not None:
                self._on_history_ready(self.context)
        except Exception as exc:
            logger.warning("History load failed %s %s: %s", self.symbol, self.timeframe, exc)

    # ── Canlı WebSocket stream ────────────────────────────────────────────
    async def _stream_ws(self) -> None:
        retry_delay = 5.0

        while True:
            try:
                logger.info("WS connecting: %s %s", self.symbol, self.timeframe)
                while True:
                    # ccxt.pro watch_ohlcv: Binance kline stream
                    ohlcv = await self.exchange.watch_ohlcv(
                        self.symbol, self.timeframe
                    )
                    if not ohlcv:
                        continue

                    for raw in ohlcv:
                        ts_ms = int(raw[0])
                        # Sadece yeni kapanan mumları işle
                        if self._last_ts is not None and ts_ms <= self._last_ts:
                            continue
                        candle = self._parse(raw, is_closed=True)
                        self.context.update(candle)
                        # _last_ts'i callback'ten önce güncelle:
                        # pipeline hatası aynı mumu tekrar işlemez
                        self._last_ts = ts_ms
                        logger.info(
                            "Candle closed: %s %s  close=%.4f",
                            self.symbol, self.timeframe, candle.close,
                        )
                        try:
                            await self._on_candle_closed(self.context, candle)
                        except Exception as exc:
                            logger.error(
                                "Pipeline error %s %s: %s",
                                self.symbol, self.timeframe, exc,
                            )

                retry_delay = 5.0   # başarılı bağlantıda reset

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "WS error %s %s: %s — retry in %.0fs",
                    self.symbol, self.timeframe, exc, retry_delay,
                )
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 120.0)  # exponential backoff, max 2dk

    def _parse(self, raw: list, is_closed: bool) -> Candle:
        ts_ms, o, h, l, c, v = raw
        return Candle(
            symbol=self.symbol,
            timeframe=self.timeframe,
            timestamp=datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone.utc),
            open=float(o),
            high=float(h),
            low=float(l),
            close=float(c),
            volume=float(v),
            is_closed=is_closed,
        )


class FixtureFeed:
    """Backtest ve demo mod için — değişmedi."""
    def __init__(
        self,
        symbol: str,
        timeframe: str,
        candles: list[Candle],
        on_candle_closed: OnCandleClosed,
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.candles = candles
        self.context = StructureContext(symbol=symbol, timeframe=timeframe)
        self._on_candle_closed = on_candle_closed

    async def run(self, delay: float = 0.0) -> None:
        for candle in self.candles:
            self.context.update(candle)
            await self._on_candle_closed(self.context, candle)
            if delay:
                await asyncio.sleep(delay)
