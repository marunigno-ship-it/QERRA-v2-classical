"""QERRA-HSR v0.1 — Core evaluation module.

Pure Python, deterministic, zero ML.
Companion physical safety layer to SEMEV-12.
"""

from dataclasses import dataclass, field
from enum import Enum
import logging
import math
from typing import Any, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# =====================================================
# Output States
# =====================================================
class HSRStatus(Enum):
    CLEAR = "CLEAR"
    MONITOR = "MONITOR"
    CRITICAL = "CRITICAL"
    HOLD = "CRITICAL"  # Fail-closed robotics alias: maps HOLD to physical CRITICAL clamp


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
    recovery_directive: str = ""
    version: str = "0.1"


# =====================================================
# Activation Thresholds (exposed for tests)
# =====================================================
DISTRESS_CRITICAL_THRESHOLD = 0.75
DISTRESS_MONITOR_THRESHOLD  = 0.45
ISOLATION_COUNT_THRESHOLD   = 1

# Numerical precision tolerance for IEEE-754 float boundaries
_FLOAT_EPSILON = 1e-6


__all__ = [
    "HSRStatus",
    "HSRInput",
    "HSRResult",
    "evaluate_hsr",
    "validate_hsr_input",
    "DISTRESS_CRITICAL_THRESHOLD",
    "DISTRESS_MONITOR_THRESHOLD",
    "ISOLATION_COUNT_THRESHOLD",
]


# =====================================================
# Telemetry Validation & Sanitization
# =====================================================
def validate_hsr_input(hsr_input: Any) -> Tuple[bool, str]:
    """
    Strictly validates HSRInput telemetry for robotics fail-closed safety.
    Rejects None, missing fields, NaN, Inf, non-numeric values, negative counts,
    and out-of-range floats.
    """
    if hsr_input is None:
        return False, "HSRInput telemetry is None (missing sensor signal)"

    required_attrs = (
        "distress_confidence",
        "persons_nearby_count",
        "hazard_proximity_flag",
        "robot_task_interruptible",
    )
    for attr in required_attrs:
        if not hasattr(hsr_input, attr):
            return False, f"Missing required telemetry field: '{attr}'"

    # 1. distress_confidence: must be float/int in [0.0, 1.0], not NaN, not Inf, not bool
    dc = getattr(hsr_input, "distress_confidence")
    if dc is None:
        return False, "distress_confidence is None"
    if isinstance(dc, bool) or not isinstance(dc, (int, float)):
        return False, f"distress_confidence must be numeric float, got {type(dc).__name__}"
    if math.isnan(dc):
        return False, "distress_confidence is NaN"
    if math.isinf(dc):
        return False, "distress_confidence is Inf"
    if dc < -_FLOAT_EPSILON or dc > (1.0 + _FLOAT_EPSILON):
        return False, f"distress_confidence={dc} out of valid range [0.0, 1.0]"

    # 2. persons_nearby_count: non-negative integer, not bool
    pc = getattr(hsr_input, "persons_nearby_count")
    if pc is None:
        return False, "persons_nearby_count is None"
    if isinstance(pc, bool) or not isinstance(pc, int):
        return False, f"persons_nearby_count must be an integer, got {type(pc).__name__}"
    if pc < 0:
        return False, f"persons_nearby_count={pc} cannot be negative"

    # 3. hazard_proximity_flag: strictly boolean
    hp = getattr(hsr_input, "hazard_proximity_flag")
    if hp is None or not isinstance(hp, bool):
        return False, f"hazard_proximity_flag must be a boolean, got {type(hp).__name__}"

    # 4. robot_task_interruptible: strictly boolean
    ri = getattr(hsr_input, "robot_task_interruptible")
    if ri is None or not isinstance(ri, bool):
        return False, f"robot_task_interruptible must be a boolean, got {type(ri).__name__}"

    return True, ""


# =====================================================
# Evaluation Function
# =====================================================
def evaluate_hsr(hsr_input: HSRInput) -> HSRResult:
    """
    Main evaluation function for QERRA-HSR v0.1.
    Pure deterministic logic — zero ML.

    Fails closed to HSRStatus.CRITICAL if telemetry is corrupted, missing,
    or out-of-bounds.
    """
    # Fail-closed guard: sanitize telemetry before any physical safety calculation
    is_valid, err_msg = validate_hsr_input(hsr_input)
    if not is_valid:
        logger.error(f"HSR | FAIL-CLOSED | {err_msg}")
        return HSRResult(
            status=HSRStatus.CRITICAL,
            vectors_activated=["telemetry_fault_fail_closed"],
            reasoning=f"FAIL-CLOSED: {err_msg}",
            recovery_directive="HOLD: Telemetry corrupted or missing. Manual confirmation required to clear.",
            version="0.1"
        )

    # Sanitize distress_confidence against floating point epsilon boundaries
    distress_conf = float(hsr_input.distress_confidence)
    if distress_conf < 0.0:
        distress_conf = 0.0
    elif distress_conf > 1.0:
        distress_conf = 1.0

    activated = []
    reasons = []

    # Pre-compute conditions
    distress_critical = distress_conf >= DISTRESS_CRITICAL_THRESHOLD
    distress_monitor = distress_conf >= DISTRESS_MONITOR_THRESHOLD
    person_isolated = hsr_input.persons_nearby_count <= ISOLATION_COUNT_THRESHOLD
    distress_isolated_combined = distress_monitor and person_isolated

    # --- HSR-V01: immediate_physical_distress ---
    if distress_critical or distress_isolated_combined:
        activated.append("immediate_physical_distress")
        if distress_critical:
            reasons.append(f"distress_confidence={distress_conf:.2f} >= CRITICAL threshold")
        else:
            reasons.append(f"distress_monitor + isolated (count={hsr_input.persons_nearby_count})")

    # Design note: human_isolation intentionally only activates alongside
    # an active distress signal (critical or monitor). Isolation alone,
    # with no distress, is normal human behavior and must NOT trigger
    # a safety flag — that would create false alarms and alarm fatigue.
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
        recovery_directive = ""
    elif distress_monitor:
        status = HSRStatus.MONITOR
        recovery_directive = ""
    else:
        status = HSRStatus.CLEAR
        if hsr_input.robot_task_interruptible:
            recovery_directive = "Clear now — resume as normal."
        else:
            recovery_directive = "Clear now, but this was interrupted mid-task — hold for a person to confirm before continuing."

    # Build reasoning
    if reasons:
        reasoning = " | ".join(reasons)
    else:
        reasoning = "No safety signals detected"

    result = HSRResult(
        status=status,
        vectors_activated=activated,
        reasoning=reasoning,
        recovery_directive=recovery_directive
    )

    logger.info(f"HSR | {result.status.value} | vectors={activated} | interruptible={hsr_input.robot_task_interruptible}")

    return result
