"""QERRA-HSR v0.1 — Core evaluation module.

This file is a stub as defined in QERRA-HSR-Design-v0.1.md (Step 1).
Full implementation will be added in Step 4.
"""

from dataclasses import dataclass
from enum import Enum


class HSRStatus(Enum):
    CLEAR = "CLEAR"
    MONITOR = "MONITOR"
    CRITICAL = "CRITICAL"


@dataclass
class HSRInput:
    distress_confidence: float      # 0.0–1.0
    persons_nearby_count: int       # upright, responsive humans
    hazard_proximity_flag: bool
    robot_task_interruptible: bool  # affects *how*, not *whether*


@dataclass
class HSRResult:
    status: HSRStatus
    vectors_activated: list[str]
    reasoning: str
    version: str = "0.1"


def evaluate_hsr(hsr_input: HSRInput) -> HSRResult:
    """Stub — full implementation follows in Step 4."""
    return HSRResult(
        status=HSRStatus.CLEAR,
        vectors_activated=[],
        reasoning="HSR evaluation stub — not yet implemented (Step 1)"
    )