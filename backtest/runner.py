from __future__ import annotations

import json
from pathlib import Path

from core.candle import Candle
from core.engine import SignalEngine


def load_fixture(path: str | Path) -> list[Candle]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Candle.model_validate(item) for item in raw]


async def run_fixture_backtest(path: str | Path, symbol: str = "BTC/USDT") -> dict:
    engine = SignalEngine(
        symbols=[symbol],
        htf=["1h"],
        ltf=["5m"],
        min_score=40,
        min_rr_ratio=2.0,
        risk_per_trade_pct=1.0,
        atr_sl_multiplier=0.5,
        enabled_scenarios=["htf_pullback_continuation"],
    )

    candles = load_fixture(path)
    htf = [c for c in candles if c.timeframe == "1h"]
    ltf = [c for c in candles if c.timeframe == "5m"]

    await engine.run_fixture(htf, symbol=symbol, timeframe="1h")
    await engine.run_fixture(ltf, symbol=symbol, timeframe="5m")

    return {
        "signals": [x.model_dump(mode="json") for x in engine.store.history],
        "stats": engine.store.stats(),
    }
