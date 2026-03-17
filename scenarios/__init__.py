from __future__ import annotations

from scenarios.base import BaseScenario
from scenarios.htf_pullback_continuation import HtfPullbackContinuationScenario

ALLOWED_SCENARIO = "htf_pullback_continuation"


def load_all_scenarios(enabled: list[str] | None = None) -> list[BaseScenario]:
    # Strategy system is intentionally hard-gated to one scenario.
    if enabled is not None and ALLOWED_SCENARIO not in enabled:
        return []
    return [HtfPullbackContinuationScenario()]
