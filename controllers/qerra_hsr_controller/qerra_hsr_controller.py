"""QERRA-HSR v0.1 — Self-contained Webots Controller for TIAGo.

This combines the HSR evaluation safety layer with the TIAGo motion loop.
Provides interactive keyboard controls to demonstrate CLEAR, MONITOR, and CRITICAL states.
"""

from controller import Robot, Keyboard
from dataclasses import dataclass, field
from enum import Enum
import logging

# Configure logging to output cleanly inside Webots
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# =====================================================
# QERRA-HSR Core Logic (DO NOT MODIFY Core Thresholds)
# =====================================================
class HSRStatus(Enum):
    CLEAR = "CLEAR"
    MONITOR = "MONITOR"
    CRITICAL = "CRITICAL"

@dataclass
class HSRInput:
    distress_confidence: float      # 0.0–1.0
    persons_nearby_count: int       # upright, responsive humans nearby
    hazard_proximity_flag: bool
    robot_task_interruptible: bool  # affects HOW, never WHETHER

@dataclass
class HSRResult:
    status: HSRStatus
    vectors_activated: list[str] = field(default_factory=list)
    reasoning: str = ""
    version: str = "0.1"

DISTRESS_CRITICAL_THRESHOLD = 0.75
DISTRESS_MONITOR_THRESHOLD  = 0.45
ISOLATION_COUNT_THRESHOLD   = 1

def evaluate_hsr(hsr_input: HSRInput) -> HSRResult:
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
        reasoning = "No safety signals detected"

    result = HSRResult(
        status=status,
        vectors_activated=activated,
        reasoning=reasoning
    )

    logger.info(f"HSR | {result.status.value} | vectors={activated} | interruptible={hsr_input.robot_task_interruptible}")
    return result


# =====================================================
# Main Webots Execution Loop
# =====================================================
def main():
    # Initialize the Robot instance
    robot = Robot()
    timestep = int(robot.getBasicTimeStep())

    # Initialize TIAGo's Keyboard interface
    keyboard = robot.getKeyboard()
    keyboard.enable(timestep)

    # Initialize TIAGo's Left and Right wheel motors
    left_motor = robot.getDevice('wheel_left_joint')
    right_motor = robot.getDevice('wheel_right_joint')
    
    # Configure velocity-control mode
    left_motor.setPosition(float('inf'))
    right_motor.setPosition(float('inf'))
    left_motor.setVelocity(0.0)
    right_motor.setVelocity(0.0)

    # Baseline HSR inputs (CLEAR state)
    distress_confidence = 0.0
    persons_nearby_count = 1
    hazard_proximity_flag = False
    robot_task_interruptible = True

    # Output interactive menu to the Webots Console
    print("\n" + "="*50)
    print("QERRA-HSR INTERACTIVE DEMO ACTIVE")
    print("Click inside the 3D window, then press these keys:")
    print("  'C' -> CLEAR: Reset to baseline. Patrol (Velocity: 2.0)")
    print("  'D' -> MONITOR: Mild distress, bystander present (Velocity: 0.5)")
    print("  'I' -> CRITICAL: Distress + Isolation (Velocity: 0.0 - STOP)")
    print("  'H' -> CRITICAL: Environmental Hazard (Velocity: 0.0 - STOP)")
    print("="*50 + "\n")

    last_status = None

    while robot.step(timestep) != -1:
        # Read keypresses from the user
        key = keyboard.getKey()
        if key != -1:
            char = chr(key).upper()
            
            if char == 'C':
                distress_confidence = 0.0
                persons_nearby_count = 1
                hazard_proximity_flag = False
                print("\n[KEYPRESS] 'C' - Reseting to baseline (CLEAR)")
                
            elif char == 'D':
                distress_confidence = 0.50    # Above MONITOR threshold (0.45)
                persons_nearby_count = 3       # Bystanders nearby (not isolated)
                hazard_proximity_flag = False
                print("\n[KEYPRESS] 'D' - Mild distress with people nearby (MONITOR)")
                
            elif char == 'I':
                distress_confidence = 0.50    # Above MONITOR threshold (0.45)
                persons_nearby_count = 1       # Isolated (<= 1)
                hazard_proximity_flag = False
                print("\n[KEYPRESS] 'I' - Moderate distress + Isolation (CRITICAL)")
                
            elif char == 'H':
                distress_confidence = 0.0
                persons_nearby_count = 1
                hazard_proximity_flag = True   # Human near industrial hazard
                print("\n[KEYPRESS] 'H' - Human entered Chemical Spill/Hazard Zone (CRITICAL)")

        # Package the simulated inputs
        hsr_input = HSRInput(
            distress_confidence=distress_confidence,
            persons_nearby_count=persons_nearby_count,
            hazard_proximity_flag=hazard_proximity_flag,
            robot_task_interruptible=robot_task_interruptible
        )

        # Evaluate safety state via QERRA-HSR
        result = evaluate_hsr(hsr_input)

        # Control TIAGo's physical motors based on QERRA's output
        if result.status == HSRStatus.CLEAR:
            left_motor.setVelocity(2.0)
            right_motor.setVelocity(2.0)
        elif result.status == HSRStatus.MONITOR:
            left_motor.setVelocity(0.5)
            right_motor.setVelocity(0.5)
        elif result.status == HSRStatus.CRITICAL:
            left_motor.setVelocity(0.0)
            right_motor.setVelocity(0.0)

        # Print state transitions directly to the Webots Console to avoid spam
        if result.status != last_status:
            print(f"\n>>> [QERRA-HSR STATUS CHANGE] : {result.status.value}")
            print(f"    Reasoning: {result.reasoning}")
            print(f"    Activated Vectors: {result.vectors_activated}")
            last_status = result.status

if __name__ == "__main__":
    main()
