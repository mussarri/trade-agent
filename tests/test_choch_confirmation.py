from __future__ import annotations

from datetime import datetime, timezone

from core.candle import Candle
from core.context import BosEvent, ChochEvent, StructureContext
from scenarios.choch_confirmation import ChochConfirmationScenario


def _candle(close: float) -> Candle:
    return Candle(
        symbol="BTC/USDT",
        timeframe="15m",
        timestamp=datetime.now(tz=timezone.utc),
        open=close * 0.999,
        high=close * 1.002,
        low=close * 0.998,
        close=close,
        volume=120,
        is_closed=True,
    )


def test_setup_requires_external_choch_plus_external_bos():
    scenario = ChochConfirmationScenario()
    htf = StructureContext(symbol="BTC/USDT", timeframe="1h")
    htf.external_structure_labels = ["HH", "HL", "HH"]
    ltf = StructureContext(symbol="BTC/USDT", timeframe="15m")
    ltf.candles.extend([_candle(100) for _ in range(20)])
    ltf.choch_events.append(
        ChochEvent(direction="bullish", timestamp=datetime.now(tz=timezone.utc), structure_kind="external", candle_index=10)
    )
    ltf.bos_events.append(
        BosEvent(
            direction="bullish",
            level=100.0,
            timestamp=datetime.now(tz=timezone.utc),
            structure_kind="external",
            displacement=True,
        )
    )
    setup = scenario.detect_setup(htf, ltf)
    assert setup is not None
    assert setup.direction == "long"


def test_trigger_close_confirm():
    scenario = ChochConfirmationScenario()
    htf = StructureContext(symbol="BTC/USDT", timeframe="1h")
    htf.external_structure_labels = ["HH", "HL", "HH"]
    ltf = StructureContext(symbol="BTC/USDT", timeframe="15m")
    ltf.candles.extend([_candle(100) for _ in range(20)])
    ts = datetime.now(tz=timezone.utc)
    ltf.choch_events.append(ChochEvent(direction="bullish", timestamp=ts, structure_kind="external", candle_index=10))
    ltf.bos_events.append(BosEvent(direction="bullish", level=100.0, timestamp=ts, structure_kind="external", displacement=True))
    setup = scenario.detect_setup(htf, ltf)
    assert setup is not None
    ltf.candles.append(_candle((setup.entry_zone_low + setup.entry_zone_high) / 2))
    trigger = scenario.detect_trigger(setup, ltf)
    assert trigger is not None
