from __future__ import annotations

from core.models import Trigger

WEIGHTS = {
    "htf_alignment":          30,   # kritik
    "fvg_or_ob_presence":     25,   # entry kalitesi
    "volume_confirmation":    20,   # momentum teyidi
    "liquidity_confluence":   15,   # güçlendirici
    "session_time":           10,   # timing
}
# Toplam: 100

ICT_FULL_SETUP_BONUS = 15
MIN_SCORE = 65
MIN_RR_RATIO = 2.5


def score(trigger: Trigger, ict_bonus: int = 0) -> int:
    total = sum(WEIGHTS.get(k, 0) for k, v in trigger.confidence_factors.items() if v)
    bonus = ict_bonus or (ICT_FULL_SETUP_BONUS if trigger.setup.meta.get("ict_bonus") else 0)
    return min(total + bonus, 100)
