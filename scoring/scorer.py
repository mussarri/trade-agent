from __future__ import annotations

from core.models import Trigger

WEIGHTS = {
    "htf_alignment":   20,
    "pullback_active": 15,
    "zone_reaction":   20,
    "displacement":    20,
    "micro_bos":       20,
    "first_pullback":   5,
}
# Total: 100

MIN_SCORE = 65
MIN_RR_RATIO = 2.0


def score(trigger: Trigger) -> int:
    total = sum(WEIGHTS.get(k, 0) for k, v in trigger.confidence_factors.items() if v)
    return min(total, 100)
