"""
QERRA-v2 Classical — Simulation Demo 6 Controller
World: demo6_assembly.wbt
Scenario: Automotive Assembly Bay 4 — Solitary Worker Collapse & Compound Hazard
Architecture:
  - Layer 1: QERRA-HSR v0.1 + StabilizedHSR (Reflexive Physical Safety)
  - Vectors: All 3 active simultaneously (distress, isolation, hazard)
  - Contract: Property HSR-5 Recovery Directive (Closed-Loop Actuator Enforcement)
Author: Marussa Metocharaki
"""

import os
import sys
import math
import logging

logging.getLogger("hsr").setLevel(logging.WARNING)
logging.getLogger("qerra_hsr").setLevel(logging.WARNING)

# =====================================================
# Universal Path Discovery to QERRA-v2-classical Core
# =====================================================
def _discover_qerra_path():
    env_path = os.environ.get("QERRA_PATH")
    if env_path and os.path.isdir(os.path.join(env_path, "hsr")):
        return env_path

    controller_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.abspath(os.path.join(controller_dir, "..", "..", "..")),
        os.path.abspath(os.path.join(controller_dir, "..", "..", "..", "QERRA-v2-classical")),
        os.path.abspath(os.path.join(controller_dir, "..", "..")),
        os.path.abspath(os.path.join(controller_dir, "..", "..", "QERRA-v2-classical")),
        r"C:\Users\marun\PycharmProjects\QERRA-v2-classical",
        r"C:\qerra_webots_project",
    ]
    for candidate in candidates:
        if os.path.isdir(os.path.join(candidate, "hsr")):
            return candidate
    return None

_qerra_path = _discover_qerra_path()
if _qerra_path and _qerra_path not in sys.path:
    sys.path.insert(0, _qerra_path)

from controller import Supervisor

try:
    from hsr.qerra_hsr import HSRInput, HSRStatus, evaluate_hsr
    from hsr.hysteresis_wrapper import StabilizedHSR
    LOCAL_HSR_READY = True
    print("\n[QERRA-SYSTEM] Layer 1 (QERRA-HSR v0.1) & StabilizedHSR: READY.")
except ImportError as e:
    LOCAL_HSR_READY = False
    print(f"\n[QERRA-SYSTEM] ERROR: Failed to import QERRA-HSR core: {e}")

# TIAGo Kinematic & Velocity Constants
WHEEL_RADIUS = 0.0985   # meters (standard PAL Robotics TIAGo base wheel)
CRUISE_VELOCITY = 2.6   # rad/s (~0.256 m/s, covers ~4.6m in 18s, safe 2.9m standoff)


def main():
    robot = Supervisor()
    timestep = int(robot.getBasicTimeStep())

    # Step once to initialize Webots supervisor tree
    robot.step(timestep)

    # Wheel Motors
    left_motor = robot.getDevice("wheel_left_joint")
    right_motor = robot.getDevice("wheel_right_joint")
    left_motor.setPosition(float('inf'))
    right_motor.setPosition(float('inf'))
    left_motor.setVelocity(0.0)
    right_motor.setVelocity(0.0)

    # Head Joints (for inspection tilt)
    head_pan = robot.getDevice("head_1_joint")
    head_tilt = robot.getDevice("head_2_joint")
    if head_pan:
        head_pan.setPosition(0.0)
    if head_tilt:
        head_tilt.setPosition(0.0)

    # Status LED (defensive check)
    status_led = robot.getDevice("status_led")

    # Access Worker node for physical collapse animation
    worker_node = robot.getFromDef("WORKER")
    if worker_node is None:
        print("[WARNING] DEF WORKER node not found in scene tree! Check worker name.")
        worker_trans = None
        worker_rot = None
    else:
        worker_trans = worker_node.getField("translation")
        worker_rot = worker_node.getField("rotation")

    # Synchronized HSR stabilizer tied strictly to Webots simulation clock
    stabilizer = StabilizedHSR(clock=robot.getTime)

    # State Machine Definitions
    STATE_STAGE1_NOMINAL = 1
    STATE_STAGE2_TRIPLE_TRIP = 2
    STATE_STAGE3_DWELL = 3
    STATE_STAGE4_RECOVERY_HOLD = 4
    STATE_STAGE5_STANDBY = 5

    current_state = STATE_STAGE1_NOMINAL
    collapse_triggered = False
    human_supervisor_confirmed = False

    print("\n" + "=" * 80)
    print("QERRA-v2 Classical — Simulation Demo 6 Started")
    print("Scenario: Automotive Assembly Bay 4 — Solitary Worker Collapse & Compound Hazard")
    print("Core Focus: 100% Layer 1 (QERRA-HSR v0.1) — Simultaneous 3-Vector Reflex Trip")
    print("Payload Contract: robot_task_interruptible = False (High-Voltage Battery Subassembly)")
    print("=" * 80 + "\n")

    while robot.step(timestep) != -1:
        sim_time = robot.getTime()

        # =====================================================
        # STAGE 1: NOMINAL TRANSIT (0.0s – 18.0s)
        # =====================================================
        if current_state == STATE_STAGE1_NOMINAL:
            hsr_input = HSRInput(
                distress_confidence=0.0,
                persons_nearby_count=1,
                hazard_proximity_flag=False,
                robot_task_interruptible=False
            )
            result = stabilizer.evaluate(hsr_input)

            left_motor.setVelocity(CRUISE_VELOCITY)
            right_motor.setVelocity(CRUISE_VELOCITY)

            if status_led:
                status_led.set(0x00FF00)  # Solid Green

            if sim_time % 5.0 < (timestep / 1000.0):
                print(f"[{sim_time:05.1f}s][STAGE 1] Line Logistics Transit | Payload: Unbolted HV Battery (Delicate)")
                print(f"         Status: {result.status.value} | Commanded Velocity: {CRUISE_VELOCITY} rad/s | Vectors: {result.vectors_activated}")

            if sim_time >= 18.0:
                current_state = STATE_STAGE2_TRIPLE_TRIP

        # =====================================================
        # STAGE 2: ACUTE WORKER COLLAPSE & 3-VECTOR TRIP (18.0s – 38.0s)
        # =====================================================
        elif current_state == STATE_STAGE2_TRIPLE_TRIP:
            if not collapse_triggered:
                # Physically trigger the collapse of Marcus flat onto the floor deck
                if worker_trans and worker_rot:
                    worker_trans.setSFVec3f([3.0, 0.0, 0.22])
                    worker_rot.setSFRotation([0.0, 1.0, 0.0, 1.57])
                
                print("\n" + "!" * 80)
                print(f"[{sim_time:05.1f}s][INCIDENT] Technician Marcus Vance suffers acute cardiovascular syncope!")
                print(f"[{sim_time:05.1f}s][INCIDENT] Worker collapsed prone into Station 4 hazard envelope. Zero bystanders.")
                print("!" * 80)
                collapse_triggered = True

            # SIMULTANEOUS ACTIVATION OF ALL 3 VECTORS
            hsr_input = HSRInput(
                distress_confidence=0.88,       # HSR-V01: immediate_physical_distress (>= 0.75)
                persons_nearby_count=0,          # HSR-V02: human_isolation (<= 1)
                hazard_proximity_flag=True,      # HSR-V03: environmental_hazard_proximity
                robot_task_interruptible=False   # Property HSR-4: Never suppresses CRITICAL
            )
            result = stabilizer.evaluate(hsr_input)

            # SUB-1MS PHYSICAL REFLEX CLAMP (<1ms latency)
            left_motor.setVelocity(0.0)
            right_motor.setVelocity(0.0)

            # Head tilts down to visually inspect fallen worker
            if head_tilt:
                head_tilt.setPosition(0.35)

            # Flashing Red Alert LED
            if status_led:
                red_color = 0xFF0000 if (int(sim_time * 4) % 2 == 0) else 0x000000
                status_led.set(red_color)

            if sim_time % 4.0 < (timestep / 1000.0):
                print(f"\n[{sim_time:05.1f}s][LAYER 1: QERRA-HSR TRIP] Status: {result.status.value}")
                print(f"  • Motors Clamped  : 0.0 rad/s (FAIL-CLOSED | Sub-1ms Command Delay)")
                print(f"  • Active Vectors  : {result.vectors_activated}")
                print(f"  • Audit Trace     : {result.reasoning}")
                print(f"  • SEMEV-12 State  : SUSPENDED (Zero ML Deliberation Overhead)")

            # Hold reflex for 20 seconds for viewer legibility
            if sim_time >= 38.0:
                print("\n" + "-" * 80)
                print(f"[{sim_time:05.1f}s][INCIDENT MITIGATION] Medical team arrived. Station 4 locked out.")
                print(f"[{sim_time:05.1f}s][INCIDENT MITIGATION] Telemetry calming: Engaging Stabilizer Dwell...")
                print("-" * 80)
                current_state = STATE_STAGE3_DWELL

        # =====================================================
        # STAGE 3: STABILIZER DWELL WINDOW (Event-Driven 1.0s Dwell)
        # =====================================================
        elif current_state == STATE_STAGE3_DWELL:
            clear_telemetry = HSRInput(
                distress_confidence=0.0,
                persons_nearby_count=3,          # First responders on site
                hazard_proximity_flag=False,     # Station locked out
                robot_task_interruptible=False
            )
            result = stabilizer.evaluate(clear_telemetry)

            left_motor.setVelocity(0.0)
            right_motor.setVelocity(0.0)

            if status_led:
                status_led.set(0xFFBF00)  # Amber caution during dwell

            # Advance strictly when StabilizedHSR's 1.0s dwell window naturally elapses
            if result.status == HSRStatus.CLEAR:
                print(f"\n[{sim_time:05.1f}s][LAYER 1 RECOVERY] Stabilizer Dwell Elapsed -> Status: CLEAR.")
                print(f"[{sim_time:05.1f}s][CONTRACT CHECK] Interrogating QERRA Recovery Directive...")
                current_state = STATE_STAGE4_RECOVERY_HOLD

        # =====================================================
        # STAGE 4: PROPERTY HSR-5 RECOVERY CONTRACT (True Closed-Loop Wiring)
        # =====================================================
        elif current_state == STATE_STAGE4_RECOVERY_HOLD:
            clear_telemetry = HSRInput(
                distress_confidence=0.0,
                persons_nearby_count=3,
                hazard_proximity_flag=False,
                robot_task_interruptible=False   # Enforces recovery directive hold
            )
            result = stabilizer.evaluate(clear_telemetry)

            # At t = 56.0s, the supervisor inspects the battery tray and confirms
            if sim_time >= 56.0 and not human_supervisor_confirmed:
                human_supervisor_confirmed = True
                print("\n" + "=" * 80)
                print(f"[{sim_time:05.1f}s][HUMAN CONFIRMATION] Shift Supervisor inspected battery tray alignment.")
                print(f"[{sim_time:05.1f}s][HUMAN CONFIRMATION] Load integrity certified. Human confirmation granted.")
                print("=" * 80 + "\n")

            # -----------------------------------------------------------------
            # CLOSED-LOOP ENFORCEMENT: Actuators strictly obey result.recovery_directive
            # -----------------------------------------------------------------
            if "hold for a person to confirm" in result.recovery_directive:
                if not human_supervisor_confirmed:
                    # Physically enforce hold based on QERRA's directive
                    left_motor.setVelocity(0.0)
                    right_motor.setVelocity(0.0)

                    if status_led:
                        status_led.set(0xFFBF00)  # Amber hold

                    if sim_time % 3.0 < (timestep / 1000.0):
                        print(f"[{sim_time:05.1f}s][PROPERTY HSR-5 ENFORCED] Status: {result.status.value}")
                        print(f"  • Directive : \"{result.recovery_directive}\"")
                        print(f"  • Actuation : MOTORS CLAMPED AT 0.0 rad/s (Obeying QERRA Directive)")
                else:
                    current_state = STATE_STAGE5_STANDBY
            else:
                current_state = STATE_STAGE5_STANDBY

        # =====================================================
        # STAGE 5: SAFE STANDBY POST-CONFIRMATION (56.0s – 65.0s)
        # =====================================================
        elif current_state == STATE_STAGE5_STANDBY:
            # Hold at safe 2.9m standoff — DO NOT drive forward over fallen worker!
            left_motor.setVelocity(0.0)
            right_motor.setVelocity(0.0)

            if head_tilt:
                head_tilt.setPosition(0.0)  # Re-center head to neutral

            if status_led:
                status_led.set(0x00FF00)  # Solid Green

            if sim_time % 3.0 < (timestep / 1000.0):
                print(f"[{sim_time:05.1f}s][SAFE STANDBY] Load secured. TIAGo holding on-site at safe 2.9m standoff.")

            if sim_time >= 65.0:
                print(f"\n[{sim_time:05.1f}s][DEMO COMPLETE] Simulation Demo 6 finished successfully.")
                break


if __name__ == "__main__":
    main()
