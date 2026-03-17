from datetime import datetime, timedelta, timezone

from core.candle import Candle
from core.context import StructureContext
from core.models import SwingPoint


def _candle(ts: datetime, o: float, h: float, l: float, c: float, v: float = 100) -> Candle:
    return Candle(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=ts,
        open=o,
        high=h,
        low=l,
        close=c,
        volume=v,
        is_closed=True,
    )


def test_bos_internal_and_external_are_separated():
    ctx = StructureContext(symbol="BTC/USDT", timeframe="15m")
    now = datetime.now(tz=timezone.utc)
    # Seed candles so displacement check has history.
    for i in range(8):
        ctx.candles.append(_candle(now + timedelta(minutes=i), 100, 101, 99, 100, 100))
    ctx.swing_highs.append(SwingPoint(index=6, price=101.0, kind="high"))
    ctx.external_swing_highs.append(SwingPoint(index=4, price=102.0, kind="high"))
    # Break internal only.
    c = _candle(now + timedelta(minutes=9), 100, 101.5, 99.5, 101.2, 100)
    ctx.candles.append(c)
    ctx._detect_bos_choch(c)
    assert ctx.last_internal_bos is not None
    assert ctx.last_external_bos is None

    # Break external.
    c2 = _candle(now + timedelta(minutes=10), 101.2, 103.5, 101.0, 103.0, 400)
    ctx.candles.append(c2)
    ctx._detect_bos_choch(c2)
    assert ctx.last_external_bos is not None
    assert ctx.last_external_bos.structure_kind == "external"


def test_choch_uses_external_structure_invalidation():
    ctx = StructureContext(symbol="BTC/USDT", timeframe="15m")
    now = datetime.now(tz=timezone.utc)
    for i in range(8):
        ctx.candles.append(_candle(now + timedelta(minutes=i), 100, 101, 99, 100, 100))
    ctx.external_swing_highs.append(SwingPoint(index=4, price=102.0, kind="high"))
    ctx.external_swing_lows.append(SwingPoint(index=5, price=98.0, kind="low"))
    ctx.external_structure_labels = ["LL", "LH", "LL"]
    c = _candle(now + timedelta(minutes=9), 100, 103.0, 99.8, 102.5, 400)
    ctx.candles.append(c)
    ctx._detect_bos_choch(c)
    assert ctx.last_choch is not None
    assert ctx.last_choch.direction == "bullish"
