from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.candle import Candle
from core.context import StructureContext
from core.models import SwingPoint
from core.structure import (
    classify_structure_labels,
    detect_confirmed_swings,
    detect_htf_structure_shift,
)


def _candles_from_hlc(
    highs: list[float],
    lows: list[float],
    *,
    closes: list[float] | None = None,
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
) -> list[Candle]:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    out: list[Candle] = []
    if closes is None:
        closes = [(h + l) / 2 for h, l in zip(highs, lows)]

    for i, (h, l, c) in enumerate(zip(highs, lows, closes)):
        prev_close = closes[i - 1] if i > 0 else c
        o = prev_close
        high = max(h, o, c)
        low = min(l, o, c)
        out.append(
            Candle(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=base + timedelta(hours=i),
                open=o,
                high=high,
                low=low,
                close=c,
                volume=100 + i,
                is_closed=True,
            )
        )
    return out


def test_confirmed_swing_high_detection():
    candles = _candles_from_hlc(
        highs=[100, 102, 104, 107, 112, 108, 105, 103, 101],
        lows=[95, 96, 98, 99, 100, 99, 97, 96, 95],
    )

    result = detect_confirmed_swings(
        candles,
        pivot_length=2,
        min_swing_distance_atr_mult=0.0,
        structure_impact_atr_mult=0.0,
        displacement_atr_mult=0.0,
    )

    assert any(s.index == 4 and s.price == 112 for s in result.swing_highs)


def test_confirmed_swing_low_detection():
    candles = _candles_from_hlc(
        highs=[110, 109, 107, 106, 105, 106, 108, 109, 111],
        lows=[105, 103, 101, 98, 94, 99, 102, 104, 106],
    )

    result = detect_confirmed_swings(
        candles,
        pivot_length=2,
        min_swing_distance_atr_mult=0.0,
        structure_impact_atr_mult=0.0,
        displacement_atr_mult=0.0,
    )

    assert any(s.index == 4 and s.price == 94 for s in result.swing_lows)


def test_noisy_small_pivots_are_filtered_out():
    candles = _candles_from_hlc(
        highs=[100, 103, 106, 109, 112, 110, 108, 110, 112.3, 110, 108, 106],
        lows=[94, 95, 97, 99, 100, 98, 97, 98, 99, 98, 97, 96],
    )

    result = detect_confirmed_swings(
        candles,
        pivot_length=2,
        min_swing_distance_atr_mult=0.7,
        structure_impact_atr_mult=0.4,
        displacement_atr_mult=0.4,
    )

    # The second nearby pivot high is too close vs ATR and should be dropped.
    assert not any(s.index == 8 for s in result.swing_highs)


def test_external_vs_internal_swing_separation():
    highs = [100, 103, 106, 109, 112, 108, 111, 107, 113, 109, 115, 110, 112, 108, 117, 111, 114, 109, 119]
    lows = [95, 96, 98, 100, 101, 99, 100, 98, 101, 99, 103, 100, 101, 99, 104, 101, 102, 100, 106]
    ctx = StructureContext(
        symbol="BTC/USDT",
        timeframe="1h",
        ltf_pivot_length=2,
        htf_pivot_length=4,
        min_swing_distance_atr_mult=0.4,
    )

    for candle in _candles_from_hlc(highs, lows):
        ctx.update(candle)

    internal_total = len(ctx.internal_swing_highs) + len(ctx.internal_swing_lows)
    external_total = len(ctx.external_swing_highs) + len(ctx.external_swing_lows)
    assert len(ctx.internal_swing_highs) > len(ctx.external_swing_highs)
    assert internal_total > external_total


def test_hh_hl_lh_ll_labeling_uses_same_type_comparison():
    highs = [
        SwingPoint(index=1, price=100, kind="high"),
        SwingPoint(index=3, price=105, kind="high"),
        SwingPoint(index=5, price=102, kind="high"),
    ]
    lows = [
        SwingPoint(index=2, price=95, kind="low"),
        SwingPoint(index=4, price=97, kind="low"),
        SwingPoint(index=6, price=94, kind="low"),
    ]

    labels = classify_structure_labels(highs, lows, equal_level_tolerance=0.0)

    assert labels.labels == ["HH", "HL", "LH", "LL"]
    assert labels.last_lh is not None and labels.last_lh.price == 102
    assert labels.last_hl is not None and labels.last_hl.price == 97


def test_bullish_htf_shift_when_close_breaks_last_external_lh():
    candle = Candle(
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        open=99.5,
        high=101.5,
        low=98.8,
        close=101.2,
        volume=100,
        is_closed=True,
    )
    shift = detect_htf_structure_shift(
        candle=candle,
        previous_trend="bearish",
        last_external_lh=SwingPoint(index=10, price=100.8, kind="high"),
        last_external_hl=None,
        use_close_for_break_confirmation=True,
    )

    assert shift is not None
    assert shift.new_trend == "bullish"
    assert shift.structure_type == "LH"


def test_bearish_htf_shift_when_close_breaks_last_external_hl():
    candle = Candle(
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        open=100.5,
        high=101.0,
        low=98.0,
        close=98.4,
        volume=100,
        is_closed=True,
    )
    shift = detect_htf_structure_shift(
        candle=candle,
        previous_trend="bullish",
        last_external_lh=None,
        last_external_hl=SwingPoint(index=11, price=99.1, kind="low"),
        use_close_for_break_confirmation=True,
    )

    assert shift is not None
    assert shift.new_trend == "bearish"
    assert shift.structure_type == "HL"


def test_no_repeated_htf_break_alert_for_same_level():
    ctx = StructureContext(symbol="BTC/USDT", timeframe="1h", use_close_for_break_confirmation=True)
    lh = SwingPoint(index=3, price=100.0, kind="high")
    ctx.last_external_lh = lh
    ctx.htf_trend = "bearish"

    c1 = Candle(
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        open=99.0,
        high=101.0,
        low=98.5,
        close=100.8,
        volume=100,
        is_closed=True,
    )
    ctx._update_htf_trend(c1)
    first = ctx.pop_pending_htf_structure_alerts()
    assert len(first) == 1

    # Force previous trend back to bearish to ensure dedupe is actually tested,
    # not only trend-gating.
    ctx.htf_trend = "bearish"
    c2 = Candle(
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp=datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
        open=100.7,
        high=101.4,
        low=100.1,
        close=101.1,
        volume=100,
        is_closed=True,
    )
    ctx._update_htf_trend(c2)
    second = ctx.pop_pending_htf_structure_alerts()
    assert second == []


def test_close_based_break_confirmation_blocks_wick_only_fake_break():
    lh = SwingPoint(index=7, price=100.0, kind="high")
    candle = Candle(
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        open=99.3,
        high=100.7,
        low=98.9,
        close=99.8,
        volume=100,
        is_closed=True,
    )

    shift_close = detect_htf_structure_shift(
        candle=candle,
        previous_trend="bearish",
        last_external_lh=lh,
        last_external_hl=None,
        use_close_for_break_confirmation=True,
    )
    shift_wick = detect_htf_structure_shift(
        candle=candle,
        previous_trend="bearish",
        last_external_lh=lh,
        last_external_hl=None,
        use_close_for_break_confirmation=False,
    )

    assert shift_close is None
    assert shift_wick is not None
    assert shift_wick.new_trend == "bullish"
