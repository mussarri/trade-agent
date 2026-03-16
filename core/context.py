from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from core.candle import Candle
from core.models import LiquidityZone, LiquiditySweepEvent, Range, VolumeSpike
from core.structure import (
    FairValueGap,
    SwingPoint,
    detect_displacement,
    detect_fvg,
    detect_range,
    detect_sweep,
    detect_swing,
    detect_volume_spike,
    market_direction,
)


@dataclass
class BosEvent:
    direction: str
    level: float
    timestamp: datetime


@dataclass
class ChochEvent:
    direction: str
    timestamp: datetime


@dataclass
class StructureContext:
    symbol: str
    timeframe: str
    lookback: int = 2
    candles: list[Candle] = field(default_factory=list)
    swing_highs: list[SwingPoint] = field(default_factory=list)
    swing_lows: list[SwingPoint] = field(default_factory=list)
    structure_labels: list[str] = field(default_factory=list)
    bos_events: list[BosEvent] = field(default_factory=list)
    choch_events: list[ChochEvent] = field(default_factory=list)
    fvgs: list[FairValueGap] = field(default_factory=list)
    equal_high_levels: list[float] = field(default_factory=list)
    equal_low_levels: list[float] = field(default_factory=list)
    # New fields
    liquidity_zones: list[LiquidityZone] = field(default_factory=list)
    volume_spikes: list[VolumeSpike] = field(default_factory=list)
    current_range: Range | None = None
    recent_sweeps: list[LiquiditySweepEvent] = field(default_factory=list)

    def update(self, candle: Candle) -> None:
        self.candles.append(candle)
        if len(self.candles) > 500:
            self.candles = self.candles[-500:]

        swing_high, swing_low = detect_swing(self.candles, self.lookback)
        if swing_high and (not self.swing_highs or self.swing_highs[-1].index != swing_high.index):
            self.swing_highs.append(swing_high)
            self._update_structure_labels("high", swing_high.price)
        if swing_low and (not self.swing_lows or self.swing_lows[-1].index != swing_low.index):
            self.swing_lows.append(swing_low)
            self._update_structure_labels("low", swing_low.price)

        self._detect_bos_choch(candle)
        self._detect_liquidity()

        fvg = detect_fvg(self.candles)
        if fvg:
            # Only track FVGs that are anchored to a displacement move.
            # The displacement candle must be the middle of the 3-candle FVG window,
            # i.e. at index len(candles) - 2.
            disp_idx = detect_displacement(self.candles)
            if disp_idx is not None and disp_idx == len(self.candles) - 2:
                self.fvgs.append(fvg)

        self._refresh_fvg_states(candle)

        # New: liquidity zones from equal levels
        self._update_liquidity_zones(candle)

        # New: volume spike detection
        spike = detect_volume_spike(self.candles)
        if spike:
            self.volume_spikes.append(spike)
            if len(self.volume_spikes) > 50:
                self.volume_spikes = self.volume_spikes[-50:]

        # New: range detection
        self.current_range = detect_range(self.candles)

    @property
    def last_close(self) -> float | None:
        return self.candles[-1].close if self.candles else None

    @property
    def trend(self) -> str:
        return market_direction(self.structure_labels)

    @property
    def last_bos(self) -> BosEvent | None:
        return self.bos_events[-1] if self.bos_events else None

    @property
    def last_choch(self) -> ChochEvent | None:
        return self.choch_events[-1] if self.choch_events else None

    @property
    def active_fvgs(self) -> list[FairValueGap]:
        return [x for x in self.fvgs if x.active]

    def _update_structure_labels(self, kind: str, price: float) -> None:
        if kind == "high":
            prev = self.swing_highs[-2].price if len(self.swing_highs) > 1 else None
            if prev is None:
                return
            self.structure_labels.append("HH" if price > prev else "LH")
        else:
            prev = self.swing_lows[-2].price if len(self.swing_lows) > 1 else None
            if prev is None:
                return
            self.structure_labels.append("HL" if price > prev else "LL")

    def _detect_bos_choch(self, candle: Candle) -> None:
        last_high = self.swing_highs[-1].price if self.swing_highs else None
        last_low = self.swing_lows[-1].price if self.swing_lows else None

        if last_high and candle.close > last_high:
            self.bos_events.append(BosEvent(direction="bullish", level=last_high, timestamp=candle.timestamp))
            if self.trend == "bearish":
                self.choch_events.append(ChochEvent(direction="bullish", timestamp=candle.timestamp))

        if last_low and candle.close < last_low:
            self.bos_events.append(BosEvent(direction="bearish", level=last_low, timestamp=candle.timestamp))
            if self.trend == "bullish":
                self.choch_events.append(ChochEvent(direction="bearish", timestamp=candle.timestamp))

    def _detect_liquidity(self) -> None:
        if len(self.swing_highs) >= 2:
            a, b = self.swing_highs[-2], self.swing_highs[-1]
            tol = max(0.001 * b.price, 1e-6)
            if abs(a.price - b.price) <= tol:
                self.equal_high_levels.append((a.price + b.price) / 2)
        if len(self.swing_lows) >= 2:
            a, b = self.swing_lows[-2], self.swing_lows[-1]
            tol = max(0.001 * b.price, 1e-6)
            if abs(a.price - b.price) <= tol:
                self.equal_low_levels.append((a.price + b.price) / 2)

    def _refresh_fvg_states(self, candle: Candle) -> None:
        for fvg in self.fvgs:
            if not fvg.active:
                continue
            if fvg.direction == "long" and candle.low <= fvg.midpoint:
                fvg.active = False
            if fvg.direction == "short" and candle.high >= fvg.midpoint:
                fvg.active = False

    def _update_liquidity_zones(self, candle: Candle) -> None:
        # Build LiquidityZone list from equal levels
        zones_from_highs = [
            LiquidityZone(price=p, kind="high")
            for p in self.equal_high_levels
        ]
        zones_from_lows = [
            LiquidityZone(price=p, kind="low")
            for p in self.equal_low_levels
        ]
        # Merge, preserving existing swept state
        existing = {z.price: z for z in self.liquidity_zones}
        new_zones: list[LiquidityZone] = []
        for z in zones_from_highs + zones_from_lows:
            if z.price in existing:
                new_zones.append(existing[z.price])
            else:
                new_zones.append(z)
        self.liquidity_zones = new_zones

        # Check for sweeps on current candle
        from core.structure import detect_sweep  # local import avoids top-level circular risk
        swept = detect_sweep(candle, self.liquidity_zones)
        if swept:
            swept.swept = True
            # "low" zone swept → price dipped below sell-side liquidity and recovered → bullish
            # "high" zone swept → price spiked above buy-side liquidity and rejected → bearish
            sweep_dir = "bullish" if swept.kind == "low" else "bearish"
            self.recent_sweeps.append(
                LiquiditySweepEvent(direction=sweep_dir, price=swept.price, timestamp=candle.timestamp)
            )
            if len(self.recent_sweeps) > 20:
                self.recent_sweeps = self.recent_sweeps[-20:]
