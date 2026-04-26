from __future__ import annotations

from scenarios.base import BaseScenario
from scenarios.forex_1h_pullback import Forex1hPullbackScenario
from scenarios.htf_pullback_continuation import HtfPullbackContinuationScenario

_REGISTRY: dict[str, BaseScenario] = {
    "htf_pullback_continuation": HtfPullbackContinuationScenario(),
    "forex_1h_pullback": Forex1hPullbackScenario(),
}


def load_all_scenarios(enabled: list[str] | None = None) -> list[BaseScenario]:
    if enabled is None:
        return [_REGISTRY["htf_pullback_continuation"]]
    return [_REGISTRY[name] for name in enabled if name in _REGISTRY]
