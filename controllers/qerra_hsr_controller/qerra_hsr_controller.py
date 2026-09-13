"""QERRA-HSR v0.1 — Integrated Webots Controller for TIAGo.

Connects the verified QERRA-HSR core evaluation module and StabilizedHSR
dwell wrapper directly to the TIAGo AMR wheel motors in Webots.
Features simulation-clock synchronization and Human-in-the-Loop recovery.
"""

from controller import Robot, Keyboard
import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =====================================================
# Universal Path Discovery to QERRA-v2-classical Core
# =====================================================
qerra_path = os.environ.get("QERRA_PATH")
if not qerra_path:
    candidates = [
        # 1. Direct repo root relative discovery (Linux, macOS, Windows)
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
        # 2. Local PyCharm developer path
        os.path.expanduser(r"C:\Users\marun\PycharmProjects\QERRA-v2-classical"),
        # 3. Fallback relative paths
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "Users", "marun", "PycharmProjects", "QERRA-v2-classical")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "QERRA-v2-classical")),
    ]
    for candidate in candidates:
        if os.path.exists(candidate) and os.path.exists(os.path.join(candidate, "hsr")):
            qerra_path = candidate
            break

if qerra_path and qerra_path not in sys.path:
    sys.path.insert(0, qerra_path)
    logger.info(f"QERRA core loaded from: {qerra_path}")
else:
    logger.warning("QERRA core path not resolved explicitly; relying on local environment.")

# Import the real, verified production modules directly
from hsr.qerra_hsr import HSRInput, HSRStatus, evaluate_hsr
from hsr.hysteresis_wrapper import StabilizedHSR


# =====================================================
# Main Webots Execution Loop
# =====================================================
def main():
    robot = Robot()
    timestep = int(robot.getBasicTimeStep())

    keyboard = robot.getKeyboard()
    keyboard.enable(timestep)

    # Initialize TIAGo's wheel motors
    left_motor = robot.getDevice('wheel_left_joint')
    right_motor = robot.getDevice('wheel_right_joint')

    left_motor.setPosition(float('inf'))
    right_motor.setPosition(float('inf'))
    left_motor.setVelocity(0.0)
    right_motor.setVelocity(0.0)

    # Use Webots simulation clock for deterministic dwell timing
    def get_sim_time():
        return robot.getTime()

    stabilizer = StabilizedHSR(clock=get_sim_time)

    # Baseline telemetry inputs
    distress_confidence = 0.0
    persons_nearby_count = 1
    hazard_proximity_flag = False
    robot_task_interruptible = True
    human_cleared_confirmation = False

    print("\n" + "=" * 60)
    print("QERRA-HSR WEBOTS CONTROLLER (v2.0.1 Synchronized)")
    print("Interactive controls (Click inside 3D window, then press):")
    print("  'C' -> CLEAR: Reset telemetry to baseline")
    print("  'D' -> MONITOR: Mild distress (Vel: 0.5)")
    print("  'I' -> CRITICAL: Distress + Isolation (Commanded Vel: 0.0)")
    print("  'H' -> CRITICAL: Environmental Hazard (Commanded Vel: 0.0)")
    print("  'T' -> TOGGLE Task Interruptible (Routine vs. Delicate)")
    print("  'K' -> HUMAN CONFIRMATION: Acknowledge & resume held task")
    print("=" * 60 + "\n")

    last_status = None
    last_directive = None

    while robot.step(timestep) != -1:
        key = keyboard.getKey()
        if key != -1:
            char = chr(key).upper()

            if char == 'C':
                distress_confidence = 0.0
                persons_nearby_count = 1
                hazard_proximity_flag = False
                human_cleared_confirmation = False
                print("\n[KEYPRESS] 'C' - Telemetry reset to baseline (CLEAR)")

            elif char == 'D':
                distress_confidence = 0.50
                persons_nearby_count = 3
                hazard_proximity_flag = False
                human_cleared_confirmation = False
                print("\n[KEYPRESS] 'D' - Mild distress with bystanders present (MONITOR)")

            elif char == 'I':
                distress_confidence = 0.50
                persons_nearby_count = 1
                hazard_proximity_flag = False
                human_cleared_confirmation = False
                print("\n[KEYPRESS] 'I' - Moderate distress + Isolation (CRITICAL)")

            elif char == 'H':
                distress_confidence = 0.0
                persons_nearby_count = 1
                hazard_proximity_flag = True
                human_cleared_confirmation = False
                print("\n[KEYPRESS] 'H' - Environmental Hazard Proximity (CRITICAL)")

            elif char == 'T':
                robot_task_interruptible = not robot_task_interruptible
                print(f"\n[KEYPRESS] 'T' - Task Interruptibility toggled: {robot_task_interruptible}")

            elif char == 'K':
                human_cleared_confirmation = True
                print("\n[KEYPRESS] 'K' - Human supervisor confirmed task resumption!")

        # Package the telemetry
        hsr_input = HSRInput(
            distress_confidence=distress_confidence,
            persons_nearby_count=persons_nearby_count,
            hazard_proximity_flag=hazard_proximity_flag,
            robot_task_interruptible=robot_task_interruptible
        )

        # Evaluate safety state via StabilizedHSR (with dwell and recovery directive)
        result = stabilizer.evaluate(hsr_input)

        # Physical motor actuation based on QERRA status & recovery directive
        if result.status == HSRStatus.CLEAR:
            # If a delicate task was interrupted, hold wheels at 0.0 until human confirmation
            if not robot_task_interruptible and not human_cleared_confirmation:
                left_motor.setVelocity(0.0)
                right_motor.setVelocity(0.0)
            else:
                left_motor.setVelocity(2.0)
                right_motor.setVelocity(2.0)
        elif result.status == HSRStatus.MONITOR:
            left_motor.setVelocity(0.5)
            right_motor.setVelocity(0.5)
        elif result.status == HSRStatus.CRITICAL:
            # Software commands instant 0.0 velocity (<1ms reflex latency)
            left_motor.setVelocity(0.0)
            right_motor.setVelocity(0.0)

        # Print state transitions cleanly to the Webots Console
        if result.status != last_status or result.recovery_directive != last_directive:
            print(f"\n>>> [QERRA-HSR STATUS] : {result.status.value}")
            print(f"    Reasoning: {result.reasoning}")
            print(f"    Vectors Activated: {result.vectors_activated}")
            if result.recovery_directive:
                print(f"    Recovery Directive: {result.recovery_directive}")
            last_status = result.status
            last_directive = result.recovery_directive


if __name__ == "__main__":
    main()
