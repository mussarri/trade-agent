from __future__ import annotations

from dataclasses import dataclass, field

from core.context import StructureContext


@dataclass
class ICTState:
    has_liquidity_zone: bool = False
    sweep_done: bool = False
    displacement_done: bool = False
    fvg_formed: bool = False
    retrace_entered: bool = False


class ICTPatternTracker:
    """Tracks the 5-step ICT pattern chain per symbol."""

    def __init__(self) -> None:
        self.state: dict[str, ICTState] = {}

    def _get(self, symbol: str) -> ICTState:
        if symbol not in self.state:
            self.state[symbol] = ICTState()
        return self.state[symbol]

    def update(self, symbol: str, ctx: StructureContext) -> None:
        s = self._get(symbol)

        # Step 1: liquidity zone exists
        s.has_liquidity_zone = bool(ctx.liquidity_zones)

        # Step 2: sweep occurred (any zone was swept)
        s.sweep_done = any(z.swept for z in ctx.liquidity_zones)

        # Step 3: displacement — BOS after sweep
        if s.sweep_done and ctx.last_bos:
            s.displacement_done = True

        # Step 4: FVG formed after displacement
        if s.displacement_done and ctx.active_fvgs:
            s.fvg_formed = True

        # Step 5: price retraced into FVG
        if s.fvg_formed and ctx.candles and ctx.active_fvgs:
            last_price = ctx.candles[-1].close
            for fvg in ctx.active_fvgs:
                if fvg.low <= last_price <= fvg.high:
                    s.retrace_entered = True
                    break

    def is_full_setup(self, symbol: str) -> bool:
        s = self._get(symbol)
        return (
            s.has_liquidity_zone
            and s.sweep_done
            and s.displacement_done
            and s.fvg_formed
            and s.retrace_entered
        )

    def reset(self, symbol: str) -> None:
        self.state[symbol] = ICTState()
