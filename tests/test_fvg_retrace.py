from __future__ import annotations

from datetime import datetime, timezone

from core.candle import Candle
from core.context import StructureContext
from core.models import LiquidityZone, Setup, VolumeSpike
from core.structure import FairValueGap
from scenarios.fvg_retrace import FvgRetraceScenario


def _candle(open_: float, high: float, low: float, close: float, volume: float = 100.0) -> Candle:
    return Candle(
        symbol="ETH/USDT",
        timeframe="15m",
        timestamp=datetime.now(tz=timezone.utc),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        is_closed=True,
    )


def test_neutral_htf_skips_setup():
    scenario = FvgRetraceScenario()
    htf = StructureContext(symbol="ETH/USDT", timeframe="1h")
    ltf = StructureContext(symbol="ETH/USDT", timeframe="15m")
    ltf.fvgs.append(FairValueGap(direction="long", low=1890.0, high=1910.0, midpoint=1900.0, active=True))
    ltf.candles.extend([_candle(1910, 1912, 1908, 1911), _candle(1911, 1920, 1895, 1898, 500), _candle(1898, 1900, 1890, 1895)])
    assert scenario.detect_setup(htf, ltf) is None


def test_trigger_requires_outside_inside_transition_and_depth():
    scenario = FvgRetraceScenario()
    setup = Setup(
        scenario_name="fvg_retrace",
        alert_type="SMART_MONEY_ENTRY",
        symbol="ETH/USDT",
        timeframe="15m",
        direction="long",
        entry_zone_low=1890.0,
        entry_zone_high=1910.0,
        swing_low=1880.0,
        swing_high=1920.0,
        invalidation_level=1885.0,
        meta={"fvg_midpoint": 1900.0, "has_displacement": True},
    )
    ltf = StructureContext(symbol="ETH/USDT", timeframe="15m")
    # previous candle not outside above zone -> should fail
    ltf.candles.append(_candle(1902, 1906, 1898, 1901))
    ltf.candles.append(_candle(1901, 1908, 1898, 1902))
    assert scenario.detect_trigger(setup, ltf) is None


def test_trigger_fires_on_valid_depth_confirmation():
    scenario = FvgRetraceScenario()
    setup = Setup(
        scenario_name="fvg_retrace",
        alert_type="SMART_MONEY_ENTRY",
        symbol="ETH/USDT",
        timeframe="15m",
        direction="long",
        entry_zone_low=1890.0,
        entry_zone_high=1910.0,
        swing_low=1880.0,
        swing_high=1920.0,
        invalidation_level=1885.0,
        meta={"fvg_midpoint": 1900.0, "has_displacement": True},
    )
    ltf = StructureContext(symbol="ETH/USDT", timeframe="15m")
    ltf.liquidity_zones.append(LiquidityZone(price=1885.0, kind="low", swept=True))
    ltf.candles.append(_candle(1922, 1925, 1918, 1921))
    ltf.candles.append(_candle(1921, 1922, 1894, 1906))
    ltf.volume_spikes.append(VolumeSpike(volume=500, avg_volume=100, ratio=5.0, timestamp=ltf.candles[-1].timestamp))
    trigger = scenario.detect_trigger(setup, ltf)
    assert trigger is not None
    assert trigger.conditions.close_confirm is True
