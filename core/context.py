from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from core.candle import Candle
from core.models import LiquiditySweepEvent, LiquidityZone, Range, VolumeSpike
from core.structure import (
    Direction,
    FairValueGap,
    SwingPoint,
    calculate_atr,
    classify_structure_labels,
    detect_confirmed_swings,
    detect_displacement,
    detect_fvg,
    detect_htf_structure_shift,
    detect_range,
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
class HtfStructureShiftEvent:
    alert_type: str
    symbol: str
    timeframe: str
    broken_level: float
    current_close: float
    previous_htf_trend: Direction
    new_htf_trend: Direction
    direction: Direction
    structure_type: str
    reason: str
    dedupe_key: str
    timestamp: datetime


@dataclass
class StructureContext:
    symbol: str
    timeframe: str
    is_ltf: bool = False

    # Legacy names preserved for compatibility.
    lookback: int = 3
    external_lookback: int = 5

    # New structure-engine configuration.
    ltf_pivot_length: int | None = None
    htf_pivot_length: int | None = None
    min_swing_distance_atr_mult: float = 0.8
    equal_level_tolerance: float = 0.001
    use_close_for_break_confirmation: bool = True
    atr_period: int = 14

    candles: list[Candle] = field(default_factory=list)

    # Internal (LTF style) structure
    internal_swing_highs: list[SwingPoint] = field(default_factory=list)
    internal_swing_lows: list[SwingPoint] = field(default_factory=list)
    internal_structure_labels: list[str] = field(default_factory=list)

    # Backward-compatible aliases consumed by existing modules
    swing_highs: list[SwingPoint] = field(default_factory=list)
    swing_lows: list[SwingPoint] = field(default_factory=list)
    structure_labels: list[str] = field(default_factory=list)

    # External (major) structure
    external_swing_highs: list[SwingPoint] = field(default_factory=list)
    external_swing_lows: list[SwingPoint] = field(default_factory=list)
    external_structure_labels: list[str] = field(default_factory=list)

    # Last relevant structure anchors
    last_internal_lh: SwingPoint | None = None
    last_internal_hl: SwingPoint | None = None
    last_external_lh: SwingPoint | None = None
    last_external_hl: SwingPoint | None = None

    # Explicit HTF trend state
    htf_trend: Direction = "neutral"
    previous_htf_trend: Direction = "neutral"

    bos_events: list[BosEvent] = field(default_factory=list)
    choch_events: list[ChochEvent] = field(default_factory=list)

    htf_structure_shift_events: list[HtfStructureShiftEvent] = field(default_factory=list)
    _pending_htf_shift_alerts: list[dict] = field(default_factory=list)
    _pending_ltf_breakout_alerts: list[dict] = field(default_factory=list)
    _last_ltf_breakout_direction: str | None = None  # "bullish" | "bearish" — tracks last alerted direction
    _htf_shift_dedupe_keys: set[str] = field(default_factory=set)
    _htf_shift_dedupe_order: list[str] = field(default_factory=list)

    fvgs: list[FairValueGap] = field(default_factory=list)
    equal_high_levels: list[float] = field(default_factory=list)
    equal_low_levels: list[float] = field(default_factory=list)
    liquidity_zones: list[LiquidityZone] = field(default_factory=list)
    volume_spikes: list[VolumeSpike] = field(default_factory=list)
    current_range: Range | None = None
    recent_sweeps: list[LiquiditySweepEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.ltf_pivot_length is None:
            self.ltf_pivot_length = max(1, self.lookback)
        if self.htf_pivot_length is None:
            self.htf_pivot_length = max(1, self.external_lookback)

    def update(self, candle: Candle) -> None:
        self.candles.append(candle)
        if len(self.candles) > 500:
            self.candles = self.candles[-500:]

        self._rebuild_swing_structure(candle)
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
        if self.htf_trend != "neutral":
            return self.htf_trend

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

    def pop_pending_htf_structure_alerts(self) -> list[dict]:
        if not self._pending_htf_shift_alerts:
            return []
        out = self._pending_htf_shift_alerts[:]
        self._pending_htf_shift_alerts.clear()
        return out

    def pop_pending_ltf_breakout_alerts(self) -> list[dict]:
        if not self._pending_ltf_breakout_alerts:
            return []
        out = self._pending_ltf_breakout_alerts[:]
        self._pending_ltf_breakout_alerts.clear()
        return out

    def _rebuild_swing_structure(self, candle: Candle) -> None:
        internal = detect_confirmed_swings(
            self.candles,
            pivot_length=max(1, int(self.ltf_pivot_length or self.lookback)),
            atr_period=max(2, int(self.atr_period)),
            min_swing_distance_atr_mult=max(0.0, self.min_swing_distance_atr_mult),
            structure_impact_atr_mult=max(0.1, self.min_swing_distance_atr_mult * 0.75),
            displacement_atr_mult=max(0.1, self.min_swing_distance_atr_mult * 0.75),
            equal_level_tolerance=max(0.0, self.equal_level_tolerance),
        )
        external = detect_confirmed_swings(
            self.candles,
            pivot_length=max(1, int(self.htf_pivot_length or self.external_lookback)),
            atr_period=max(2, int(self.atr_period)),
            min_swing_distance_atr_mult=max(0.0, self.min_swing_distance_atr_mult * 1.4),
            structure_impact_atr_mult=max(0.1, self.min_swing_distance_atr_mult * 1.1),
            displacement_atr_mult=max(0.1, self.min_swing_distance_atr_mult * 1.1),
            equal_level_tolerance=max(0.0, self.equal_level_tolerance),
        )

        self.internal_swing_highs = internal.swing_highs
        self.internal_swing_lows = internal.swing_lows
        self.swing_highs = list(self.internal_swing_highs)
        self.swing_lows = list(self.internal_swing_lows)

        self.external_swing_highs = external.swing_highs
        self.external_swing_lows = external.swing_lows

        internal_labels = classify_structure_labels(
            self.internal_swing_highs,
            self.internal_swing_lows,
            equal_level_tolerance=max(0.0, self.equal_level_tolerance),
        )
        external_labels = classify_structure_labels(
            self.external_swing_highs,
            self.external_swing_lows,
            equal_level_tolerance=max(0.0, self.equal_level_tolerance),
        )

        self.internal_structure_labels = list(internal_labels.labels)
        self.structure_labels = list(self.internal_structure_labels)
        self.external_structure_labels = list(external_labels.labels)

        self.last_internal_lh = internal_labels.last_lh
        self.last_internal_hl = internal_labels.last_hl
        self.last_external_lh = external_labels.last_lh
        self.last_external_hl = external_labels.last_hl

        self.equal_high_levels = sorted(
            {
                *[round(x, 8) for x in internal.equal_high_levels],
                *[round(x, 8) for x in external.equal_high_levels],
            }
        )
        self.equal_low_levels = sorted(
            {
                *[round(x, 8) for x in internal.equal_low_levels],
                *[round(x, 8) for x in external.equal_low_levels],
            }
        )

        self._update_htf_trend(candle)

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
        if structure_kind == "internal" and self.is_ltf:
            # Only alert when direction alternates: high→low or low→high sequence required
            if self._last_ltf_breakout_direction is None or self._last_ltf_breakout_direction != direction:
                is_high_break = direction == "bullish"
                self._last_ltf_breakout_direction = direction
                self._pending_ltf_breakout_alerts.append(
                    {
                        "type": "LTF_BREAKOUT",
                        "alert_type": "LTF_5M_HIGH_BREAKOUT" if is_high_break else "LTF_5M_LOW_BREAKOUT",
                        "symbol": self.symbol,
                        "pair": self.symbol.replace("/", ""),
                        "timeframe": self.timeframe,
                        "timeframe_ltf": self.timeframe,
                        "direction": "long" if is_high_break else "short",
                        "broken_level": level,
                        "current_close": candle.close,
                        "displacement": displacement,
                        "reason": f"5m close broke internal swing {'high' if is_high_break else 'low'}",
                        "timestamp": candle.timestamp.isoformat(),
                    }
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
        last_high = self.internal_swing_highs[-1].price if self.internal_swing_highs else None
        last_low = self.internal_swing_lows[-1].price if self.internal_swing_lows else None
        ext_last_high = self.external_swing_highs[-1].price if self.external_swing_highs else None
        ext_last_low = self.external_swing_lows[-1].price if self.external_swing_lows else None
        ext_trend_before = self.previous_htf_trend

        displacement_idx = detect_displacement(self.candles)
        is_displacement_bar = displacement_idx == len(self.candles) - 1

        if last_high is not None and candle.close > last_high:
            self._append_bos_if_new(
                candle=candle,
                direction="bullish",
                level=last_high,
                structure_kind="internal",
                displacement=is_displacement_bar,
            )
        if last_low is not None and candle.close < last_low:
            self._append_bos_if_new(
                candle=candle,
                direction="bearish",
                level=last_low,
                structure_kind="internal",
                displacement=is_displacement_bar,
            )

        if ext_last_high is not None and candle.close > ext_last_high:
            self._append_bos_if_new(
                candle=candle,
                direction="bullish",
                level=ext_last_high,
                structure_kind="external",
                displacement=is_displacement_bar,
            )
            if ext_trend_before == "bearish":
                self._append_choch_if_new(candle=candle, direction="bullish")

        if ext_last_low is not None and candle.close < ext_last_low:
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
        if len(self.internal_swing_highs) >= 2:
            a, b = self.internal_swing_highs[-2], self.internal_swing_highs[-1]
            tol = max(self.equal_level_tolerance * b.price, 1e-6)
            if abs(a.price - b.price) <= tol:
                self.equal_high_levels.append(round((a.price + b.price) / 2, 8))

        if len(self.internal_swing_lows) >= 2:
            a, b = self.internal_swing_lows[-2], self.internal_swing_lows[-1]
            tol = max(self.equal_level_tolerance * b.price, 1e-6)
            if abs(a.price - b.price) <= tol:
                self.equal_low_levels.append(round((a.price + b.price) / 2, 8))

        self.equal_high_levels = sorted(set(self.equal_high_levels))[-80:]
        self.equal_low_levels = sorted(set(self.equal_low_levels))[-80:]

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
        existing = {(z.kind, round(z.price, 8)): z for z in self.liquidity_zones}
        new_zones: list[LiquidityZone] = []
        for z in zones_from_highs + zones_from_lows:
            key = (z.kind, round(z.price, 8))
            if key in existing:
                new_zones.append(existing[key])
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

    def _update_htf_trend(self, candle: Candle) -> None:
        self.previous_htf_trend = self.htf_trend

        shift = detect_htf_structure_shift(
            candle=candle,
            previous_trend=self.htf_trend,
            last_external_lh=self.last_external_lh,
            last_external_hl=self.last_external_hl,
            use_close_for_break_confirmation=self.use_close_for_break_confirmation,
        )

        if shift is not None:
            dedupe_key = self._build_htf_shift_dedupe_key(
                structure_type=shift.structure_type,
                direction=shift.direction,
                level=shift.broken_level,
            )
            if dedupe_key not in self._htf_shift_dedupe_keys:
                self._remember_htf_shift_dedupe_key(dedupe_key)
                self.htf_trend = shift.new_trend
                alert_type = (
                    "HTF_STRUCTURE_SHIFT_BULLISH"
                    if shift.new_trend == "bullish"
                    else "HTF_STRUCTURE_SHIFT_BEARISH"
                )
                reason_text = (
                    f"{self.timeframe} close broke last external {shift.structure_type}"
                    f" -> HTF trend shifted {shift.new_trend}"
                )
                evt = HtfStructureShiftEvent(
                    alert_type=alert_type,
                    symbol=self.symbol,
                    timeframe=self.timeframe,
                    broken_level=shift.broken_level,
                    current_close=candle.close,
                    previous_htf_trend=shift.previous_trend,
                    new_htf_trend=shift.new_trend,
                    direction=shift.direction,
                    structure_type=shift.structure_type,
                    reason=reason_text,
                    dedupe_key=dedupe_key,
                    timestamp=candle.timestamp,
                )
                self.htf_structure_shift_events.append(evt)
                if len(self.htf_structure_shift_events) > 100:
                    self.htf_structure_shift_events = self.htf_structure_shift_events[-100:]
                self._pending_htf_shift_alerts.append(
                    {
                        "type": "HTF_STRUCTURE_SHIFT",
                        "alert_type": alert_type,
                        "symbol": self.symbol,
                        "pair": self.symbol.replace("/", ""),
                        "timeframe": self.timeframe,
                        "timeframe_htf": self.timeframe,
                        "direction": shift.new_trend,
                        "broken_level": shift.broken_level,
                        "current_close": candle.close,
                        "previous_htf_trend": shift.previous_trend,
                        "new_htf_trend": shift.new_trend,
                        "reason": reason_text,
                        "structure_type": shift.structure_type,
                        "dedupe_key": dedupe_key,
                        "timestamp": candle.timestamp.isoformat(),
                    }
                )
            return

        fallback = self._fallback_trend_from_structure()
        if self.htf_trend == "neutral" and fallback != "neutral":
            self.htf_trend = fallback

    def _fallback_trend_from_structure(self) -> Direction:
        ext = market_direction(self.external_structure_labels)
        if ext != "neutral":
            return ext

        if len(self.candles) < 20:
            return "neutral"

        closes = [c.close for c in self.candles[-20:]]
        ma = sum(closes) / len(closes)
        atr = max(calculate_atr(self.candles[-20:], period=min(14, len(self.candles[-20:]))), 1e-9)
        last = closes[-1]

        if last >= ma + atr * 0.25:
            return "bullish"
        if last <= ma - atr * 0.25:
            return "bearish"
        return "neutral"

    def _build_htf_shift_dedupe_key(self, *, structure_type: str, direction: str, level: float) -> str:
        return f"{self.symbol}:{self.timeframe}:{structure_type}:{direction}:{level:.8f}"

    def _remember_htf_shift_dedupe_key(self, key: str) -> None:
        self._htf_shift_dedupe_keys.add(key)
        self._htf_shift_dedupe_order.append(key)
        if len(self._htf_shift_dedupe_order) > 500:
            stale = self._htf_shift_dedupe_order.pop(0)
            self._htf_shift_dedupe_keys.discard(stale)
