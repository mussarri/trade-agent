from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable

import httpx

from core.candle import Candle
from core.context import StructureContext

logger = logging.getLogger(__name__)

TD_BASE_URL = "https://api.twelvedata.com"

OnCandleClosed = Callable[[StructureContext, Candle], Awaitable[None]]
OnHistoryReady = Callable[[StructureContext], None]


class TwelveDataFeed:
    """Polls Twelve Data REST API for closed OHLCV candles.

    Loads history at startup, then wakes up 90 seconds after each candle
    close to fetch the just-closed bar for forex/commodity instruments like
    XAU/USD and EUR/USD.
    """

    def __init__(
        self,
        symbol: str,
        interval: str,
        api_key: str,
        on_candle_closed: OnCandleClosed,
        on_history_ready: OnHistoryReady | None = None,
        context_kwargs: dict | None = None,
        is_ltf: bool = False,
    ) -> None:
        self.symbol = symbol
        self.interval = interval
        self.api_key = api_key
        self.context = StructureContext(
            symbol=symbol, timeframe=interval, is_ltf=is_ltf, **(context_kwargs or {})
        )
        self._on_candle_closed = on_candle_closed
        self._on_history_ready = on_history_ready
        self._last_ts: datetime | None = None

    async def start(self, history_limit: int = 200) -> None:
        await self._load_history(history_limit)
        await self._poll_loop()

    # ── History ──────────────────────────────────────────────────────────────

    async def _load_history(self, limit: int) -> None:
        try:
            candles = await self._fetch_ohlcv(outputsize=limit)
            # Skip the last candle — it may still be forming.
            for c in candles[:-1]:
                self.context.update(c)
                if self._last_ts is None or c.timestamp > self._last_ts:
                    self._last_ts = c.timestamp
            logger.info(
                "TwelveData history loaded: %s %s  bars=%d",
                self.symbol,
                self.interval,
                len(candles) - 1,
            )
            if self._on_history_ready is not None:
                self._on_history_ready(self.context)
        except Exception as exc:
            logger.warning(
                "TwelveData history failed %s %s: %s", self.symbol, self.interval, exc
            )

    # ── Live polling ─────────────────────────────────────────────────────────

    async def _poll_loop(self) -> None:
        retry_delay = 30.0

        while True:
            try:
                wait = self._seconds_until_next_close()
                logger.debug(
                    "TwelveData %s: next poll in %.0fs", self.symbol, wait
                )
                await asyncio.sleep(wait)

                # Fetch last 3 bars: [H-2, H-1 (just closed), H (forming)]
                candles = await self._fetch_ohlcv(outputsize=3)

                # Process all closed bars we haven't seen yet (skip last = forming).
                for c in candles[:-1]:
                    if self._last_ts is not None and c.timestamp <= self._last_ts:
                        continue
                    self._last_ts = c.timestamp
                    self.context.update(c)
                    logger.info(
                        "TwelveData candle closed: %s %s  close=%.5f",
                        self.symbol,
                        self.interval,
                        c.close,
                    )
                    try:
                        await self._on_candle_closed(self.context, c)
                    except Exception as exc:
                        logger.error(
                            "Pipeline error %s %s: %s", self.symbol, self.interval, exc
                        )

                retry_delay = 30.0

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "TwelveData poll error %s %s: %s — retry in %.0fs",
                    self.symbol,
                    self.interval,
                    exc,
                    retry_delay,
                )
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 300.0)

    def _seconds_until_next_close(self) -> float:
        """Return seconds until 90s after the next interval boundary."""
        now = datetime.now(tz=timezone.utc)
        interval_minutes = self._interval_minutes()
        # Align to next boundary of interval_minutes
        total_minutes = now.hour * 60 + now.minute
        remainder = total_minutes % interval_minutes
        minutes_to_next = (interval_minutes - remainder) % interval_minutes
        if minutes_to_next == 0:
            minutes_to_next = interval_minutes
        next_boundary = now.replace(second=0, microsecond=0) + timedelta(
            minutes=minutes_to_next
        )
        target = next_boundary + timedelta(seconds=90)
        delta = (target - now).total_seconds()
        return max(delta, 5.0)

    def _interval_minutes(self) -> int:
        mapping = {
            "1min": 1,
            "5min": 5,
            "15min": 15,
            "30min": 30,
            "45min": 45,
            "1h": 60,
            "2h": 120,
            "4h": 240,
            "8h": 480,
            "1day": 1440,
        }
        return mapping.get(self.interval, 60)

    # ── REST fetch ───────────────────────────────────────────────────────────

    async def _fetch_ohlcv(self, outputsize: int = 200) -> list[Candle]:
        params = {
            "symbol": self.symbol,
            "interval": self.interval,
            "outputsize": outputsize,
            "apikey": self.api_key,
            "timezone": "UTC",
            "order": "ASC",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{TD_BASE_URL}/time_series", params=params)
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") == "error":
            raise RuntimeError(
                f"TwelveData API error for {self.symbol}: {data.get('message')}"
            )

        values = data.get("values", [])
        if not values:
            raise RuntimeError(f"TwelveData returned no values for {self.symbol}")

        return [self._parse(v) for v in values]

    def _parse(self, raw: dict) -> Candle:
        ts = datetime.strptime(raw["datetime"], "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
        return Candle(
            symbol=self.symbol,
            timeframe=self.interval,
            timestamp=ts,
            open=float(raw["open"]),
            high=float(raw["high"]),
            low=float(raw["low"]),
            close=float(raw["close"]),
            volume=float(raw.get("volume", 0.0)),
            is_closed=True,
        )
