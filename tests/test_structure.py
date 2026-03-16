from datetime import datetime, timedelta, timezone

from core.candle import Candle
from core.context import StructureContext


def test_context_updates_basic():
    ctx = StructureContext(symbol="BTC/USDT", timeframe="15m")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    values = [
        (100, 103, 99, 102),
        (102, 104, 100, 103),
        (103, 107, 102, 106),
        (106, 106.5, 101, 102),
        (102, 103, 97, 98),
        (98, 99, 95, 96),
        (96, 101, 95.5, 100),
    ]

    for i, (o, h, l, c) in enumerate(values):
        ctx.update(
            Candle(
                symbol="BTC/USDT",
                timeframe="15m",
                timestamp=start + timedelta(minutes=15 * i),
                open=o,
                high=h,
                low=l,
                close=c,
                volume=100 + i,
                is_closed=True,
            )
        )

    assert len(ctx.candles) == len(values)
    assert ctx.trend in {"bullish", "bearish", "neutral"}
