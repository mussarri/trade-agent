from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from core.candle import Candle
from core.models import LiquiditySweepEvent, LiquidityZone, Range, VolumeSpike
from core.structure import (
    FairValueGap,
    SwingPoint,
    detect_displacement,
    detect_fvg,
    detect_range,
    detect_swing,
    detect_volume_spike,
    market_direction,
)


@dataclass
class BosEvent:
    direction: str
    level: float
    timestamp: datetime
    structure_kind: str = "internal"  # "internal" | "external"
    candle_index: int = -1
    displacement: bool = False


@dataclass
class ChochEvent:
    direction: str
    timestamp: datetime
    structure_kind: str = "external"
    candle_index: int = -1


@dataclass
class StructureContext:
    symbol: str
    timeframe: str
    lookback: int = 2
    external_lookback: int = 6
    candles: list[Candle] = field(default_factory=list)
    swing_highs: list[SwingPoint] = field(default_factory=list)
    swing_lows: list[SwingPoint] = field(default_factory=list)
    external_swing_highs: list[SwingPoint] = field(default_factory=list)
    external_swing_lows: list[SwingPoint] = field(default_factory=list)
    structure_labels: list[str] = field(default_factory=list)
    external_structure_labels: list[str] = field(default_factory=list)
    bos_events: list[BosEvent] = field(default_factory=list)
    choch_events: list[ChochEvent] = field(default_factory=list)
    fvgs: list[FairValueGap] = field(default_factory=list)
    equal_high_levels: list[float] = field(default_factory=list)
    equal_low_levels: list[float] = field(default_factory=list)
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

        ext_high, ext_low = detect_swing(self.candles, self.external_lookback)
        if ext_high and (not self.external_swing_highs or self.external_swing_highs[-1].index != ext_high.index):
            self.external_swing_highs.append(ext_high)
            self._update_external_structure_labels("high", ext_high.price)
        if ext_low and (not self.external_swing_lows or self.external_swing_lows[-1].index != ext_low.index):
            self.external_swing_lows.append(ext_low)
            self._update_external_structure_labels("low", ext_low.price)

        self._detect_bos_choch(candle)
        self._detect_liquidity()

        fvg = detect_fvg(self.candles)
        if fvg:
            disp_idx = detect_displacement(self.candles)
            if disp_idx is not None and disp_idx == len(self.candles) - 2:
                self.fvgs.append(fvg)

        self._refresh_fvg_states(candle)
        self._update_liquidity_zones(candle)

        spike = detect_volume_spike(self.candles)
        if spike:
            self.volume_spikes.append(spike)
            if len(self.volume_spikes) > 50:
                self.volume_spikes = self.volume_spikes[-50:]

        self.current_range = detect_range(self.candles)

    @property
    def last_close(self) -> float | None:
        return self.candles[-1].close if self.candles else None

    @property
    def trend(self) -> str:
        ext = market_direction(self.external_structure_labels)
        if ext != "neutral":
            return ext
        return market_direction(self.structure_labels)

    @property
    def last_bos(self) -> BosEvent | None:
        return self.bos_events[-1] if self.bos_events else None

    @property
    def last_external_bos(self) -> BosEvent | None:
        for evt in reversed(self.bos_events):
            if evt.structure_kind == "external":
                return evt
        return None

    @property
    def last_internal_bos(self) -> BosEvent | None:
        for evt in reversed(self.bos_events):
            if evt.structure_kind == "internal":
                return evt
        return None

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

    def _update_external_structure_labels(self, kind: str, price: float) -> None:
        if kind == "high":
            prev = self.external_swing_highs[-2].price if len(self.external_swing_highs) > 1 else None
            if prev is None:
                return
            self.external_structure_labels.append("HH" if price > prev else "LH")
        else:
            prev = self.external_swing_lows[-2].price if len(self.external_swing_lows) > 1 else None
            if prev is None:
                return
            self.external_structure_labels.append("HL" if price > prev else "LL")

    @staticmethod
    def _is_duplicate_break(events: list[BosEvent], direction: str, level: float, structure_kind: str) -> bool:
        tol = max(abs(level) * 0.0005, 1e-9)
        for evt in reversed(events[-6:]):
            if evt.direction == direction and evt.structure_kind == structure_kind and abs(evt.level - level) <= tol:
                return True
        return False

    def _append_bos_if_new(
        self,
        *,
        candle: Candle,
        direction: str,
        level: float,
        structure_kind: str,
        displacement: bool,
    ) -> None:
        if self._is_duplicate_break(self.bos_events, direction, level, structure_kind):
            return
        self.bos_events.append(
            BosEvent(
                direction=direction,
                level=level,
                timestamp=candle.timestamp,
                structure_kind=structure_kind,
                candle_index=len(self.candles) - 1,
                displacement=displacement,
            )
        )

    def _append_choch_if_new(self, *, candle: Candle, direction: str) -> None:
        if self.choch_events and self.choch_events[-1].direction == direction:
            if (len(self.candles) - 1) - self.choch_events[-1].candle_index <= 3:
                return
        self.choch_events.append(
            ChochEvent(
                direction=direction,
                timestamp=candle.timestamp,
                structure_kind="external",
                candle_index=len(self.candles) - 1,
            )
        )

    def _detect_bos_choch(self, candle: Candle) -> None:
        last_high = self.swing_highs[-1].price if self.swing_highs else None
        last_low = self.swing_lows[-1].price if self.swing_lows else None
        ext_last_high = self.external_swing_highs[-1].price if self.external_swing_highs else None
        ext_last_low = self.external_swing_lows[-1].price if self.external_swing_lows else None
        ext_trend_before = market_direction(self.external_structure_labels)
        displacement_idx = detect_displacement(self.candles)
        is_displacement_bar = displacement_idx == len(self.candles) - 1

        if last_high and candle.close > last_high:
            self._append_bos_if_new(
                candle=candle,
                direction="bullish",
                level=last_high,
                structure_kind="internal",
                displacement=is_displacement_bar,
            )
        if last_low and candle.close < last_low:
            self._append_bos_if_new(
                candle=candle,
                direction="bearish",
                level=last_low,
                structure_kind="internal",
                displacement=is_displacement_bar,
            )

        if ext_last_high and candle.close > ext_last_high:
            self._append_bos_if_new(
                candle=candle,
                direction="bullish",
                level=ext_last_high,
                structure_kind="external",
                displacement=is_displacement_bar,
            )
            if ext_trend_before == "bearish":
                self._append_choch_if_new(candle=candle, direction="bullish")

        if ext_last_low and candle.close < ext_last_low:
            self._append_bos_if_new(
                candle=candle,
                direction="bearish",
                level=ext_last_low,
                structure_kind="external",
                displacement=is_displacement_bar,
            )
            if ext_trend_before == "bullish":
                self._append_choch_if_new(candle=candle, direction="bearish")

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
        zones_from_highs = [LiquidityZone(price=p, kind="high") for p in self.equal_high_levels]
        zones_from_lows = [LiquidityZone(price=p, kind="low") for p in self.equal_low_levels]
        existing = {z.price: z for z in self.liquidity_zones}
        new_zones: list[LiquidityZone] = []
        for z in zones_from_highs + zones_from_lows:
            if z.price in existing:
                new_zones.append(existing[z.price])
            else:
                new_zones.append(z)
        self.liquidity_zones = new_zones

        from core.structure import detect_sweep  # local import avoids top-level circular risk

        swept = detect_sweep(candle, self.liquidity_zones)
        if swept:
            swept.swept = True
            sweep_dir = "bullish" if swept.kind == "low" else "bearish"
            self.recent_sweeps.append(
                LiquiditySweepEvent(direction=sweep_dir, price=swept.price, timestamp=candle.timestamp)
            )
            if len(self.recent_sweeps) > 20:
                self.recent_sweeps = self.recent_sweeps[-20:]
