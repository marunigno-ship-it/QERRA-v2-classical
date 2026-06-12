"""QERRA-HSR v0.1 — Core evaluation module.

Pure Python, deterministic, zero ML.
Companion physical safety layer to SEMEV-12.
"""

from dataclasses import dataclass, field
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# =====================================================
# Output States
# =====================================================
class HSRStatus(Enum):
    CLEAR = "CLEAR"
    MONITOR = "MONITOR"
    CRITICAL = "CRITICAL"


# =====================================================
# Input Interface
# =====================================================
@dataclass
class HSRInput:
    """Normalized sensor signals from the robot's perception stack."""
    distress_confidence: float      # 0.0–1.0
    persons_nearby_count: int       # upright, responsive humans nearby
    hazard_proximity_flag: bool
    robot_task_interruptible: bool  # affects HOW, never WHETHER


# =====================================================
# Output Structure
# =====================================================
@dataclass
class HSRResult:
    status: HSRStatus
    vectors_activated: list[str] = field(default_factory=list)
    reasoning: str = ""
    version: str = "0.1"


# =====================================================
# Activation Thresholds (exposed for tests)
# =====================================================
DISTRESS_CRITICAL_THRESHOLD = 0.75
DISTRESS_MONITOR_THRESHOLD  = 0.45
ISOLATION_COUNT_THRESHOLD   = 1


__all__ = [
    "HSRStatus",
    "HSRInput",
    "HSRResult",
    "evaluate_hsr",
    "DISTRESS_CRITICAL_THRESHOLD",
    "DISTRESS_MONITOR_THRESHOLD",
    "ISOLATION_COUNT_THRESHOLD",
]


# =====================================================
# Evaluation Function
# =====================================================
def evaluate_hsr(hsr_input: HSRInput) -> HSRResult:
    """
    Main evaluation function for QERRA-HSR v0.1.
    Pure deterministic logic — no ML.
    """
    activated = []
    reasons = []

    # Pre-compute conditions
    distress_critical = hsr_input.distress_confidence >= DISTRESS_CRITICAL_THRESHOLD
    distress_monitor = hsr_input.distress_confidence >= DISTRESS_MONITOR_THRESHOLD
    person_isolated = hsr_input.persons_nearby_count <= ISOLATION_COUNT_THRESHOLD
    distress_isolated_combined = distress_monitor and person_isolated

    # --- HSR-V01: immediate_physical_distress ---
    if distress_critical or distress_isolated_combined:
        activated.append("immediate_physical_distress")
        if distress_critical:
            reasons.append(f"distress_confidence={hsr_input.distress_confidence:.2f} >= CRITICAL threshold")
        else:
            reasons.append(f"distress_monitor + isolated (count={hsr_input.persons_nearby_count})")

    # --- HSR-V02: human_isolation ---
    if (distress_critical or distress_monitor) and person_isolated:
        activated.append("human_isolation")
        reasons.append(f"person_isolated (count={hsr_input.persons_nearby_count}) with distress signal")

    # --- HSR-V03: environmental_hazard_proximity ---
    if hsr_input.hazard_proximity_flag:
        activated.append("environmental_hazard_proximity")
        reasons.append("hazard_proximity_flag=True")

    # Determine final status
    is_critical = distress_critical or hsr_input.hazard_proximity_flag or distress_isolated_combined

    if is_critical:
        status = HSRStatus.CRITICAL
    elif distress_monitor:
        status = HSRStatus.MONITOR
    else:
        status = HSRStatus.CLEAR

    # Build reasoning
    if reasons:
        reasoning = " | ".join(reasons)
    else:
        reasoning = "No safety signals detected"   # ← Fixed to match test

    result = HSRResult(
        status=status,
        vectors_activated=activated,
        reasoning=reasoning
    )

    logger.info(f"HSR | {result.status.value} | vectors={activated} | interruptible={hsr_input.robot_task_interruptible}")

    return result