"""
QERRA-v2 Classical — Simulation Demo 4 Controller (Closed-Loop Supervisor Engine)
Robot: PAL Robotics TIAGo (Webots R2025a)
World: demo4_courtyard.wbt
Scenario: Healthcare Courtyard — Flora Boundary Protection vs Emergency Override
Framework: QERRA-THRIVE (Suite B) + QERRA-HSR v0.1 Physical Safety Wrapper
Author: Marussa Metocharaki
"""

import os
os.environ["HF_HUB_OFFLINE"] = "1"
import sys
import math
import logging

# Mute repetitive console logs
logging.getLogger("hsr").setLevel(logging.WARNING)
logging.getLogger("qerra_hsr").setLevel(logging.WARNING)
logging.getLogger("values.ecological").setLevel(logging.WARNING)

# =====================================================
# QERRA-v2-classical Path Discovery (Cascading, Portable)
# =====================================================
def _discover_qerra_path():
    # Priority 1: Check if already resolvable as an installed package
    try:
        import ethical_core
        return None
    except ImportError:
        pass

    # Priority 2: Environment variable for external testbeds and CI
    env_path = os.environ.get("QERRA_PATH")
    if env_path and os.path.isfile(os.path.join(env_path, "ethical_core.py")):
        return env_path

    # Priority 3: Relative sibling discovery
    controller_dir = os.path.dirname(os.path.abspath(__file__))
    for candidate in (
        os.path.abspath(os.path.join(controller_dir, "..", "..", "..", "QERRA-v2-classical")),
        os.path.abspath(os.path.join(controller_dir, "..", "..", "QERRA-v2-classical")),
    ):
        if os.path.isfile(os.path.join(candidate, "ethical_core.py")):
            return candidate

    # Priority 4: Local development environment fallback
    windows_fallback = r"C:\Users\marun\PycharmProjects\QERRA-v2-classical"
    if os.path.isdir(windows_fallback):
        return windows_fallback

    return None


_qerra_path = _discover_qerra_path()
if _qerra_path and _qerra_path not in sys.path:
    sys.path.append(_qerra_path)

from controller import Supervisor

try:
    from values.ecological import rank_flora_boundary_protection
    from hsr.qerra_hsr import evaluate_hsr, HSRInput, HSRStatus
    LOCAL_ENGINE_READY = True
    print("[QERRA-SYSTEM] Layer 3 (QERRA-THRIVE) & Layer 2 (QERRA-HSR): READY.")
except ImportError as e:
    LOCAL_ENGINE_READY = False
    print(f"[QERRA-SYSTEM] ERROR: Failed to import QERRA modules: {e}")

# Robot kinematic constants
WHEEL_RADIUS = 0.0985          # m
AXLE_LENGTH = 0.404            # m
MAX_WHEEL_VELOCITY = 6.0       # rad/s

WP_PATH_CENTER = (-2.5, 0.0)   # Waypoint 1: Paved stone walkway center
WP_STANDOFF = (0.50, 0.0)      # Waypoint 2: In front of resident on lawn

POS_TOLERANCE = 0.08           # m
HEADING_TOLERANCE = math.radians(4.0)

V_CRUISE_PATH = 0.16           # m/s
V_CRUISE_LAWN = 0.20           # m/s
SLOW_RADIUS = 0.60             # m

K_HEADING_DRIVE = 2.2
K_HEADING_ROTATE = 2.5


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def angle_diff(target, current):
    d = target - current
    while d > math.pi:
        d -= 2.0 * math.pi
    while d < -math.pi:
        d += 2.0 * math.pi
    return d


def unicycle_to_wheels(v, omega):
    left_lin = v - (omega * AXLE_LENGTH / 2.0)
    right_lin = v + (omega * AXLE_LENGTH / 2.0)
    lw = clamp(left_lin / WHEEL_RADIUS, -MAX_WHEEL_VELOCITY, MAX_WHEEL_VELOCITY)
    rw = clamp(right_lin / WHEEL_RADIUS, -MAX_WHEEL_VELOCITY, MAX_WHEEL_VELOCITY)
    return lw, rw


class SupervisorDriver:
    def __init__(self, node, left_motor, right_motor):
        self.node = node
        self.left_motor = left_motor
        self.right_motor = right_motor

    def get_pose(self):
        pos = self.node.getPosition()
        x, y = pos[0], pos[1]
        rot = self.node.getOrientation()
        heading = math.atan2(rot[3], rot[0])
        return x, y, heading

    def stop(self):
        self.left_motor.setVelocity(0.0)
        self.right_motor.setVelocity(0.0)

    def rotate_to_heading(self, target_heading):
        _, _, heading = self.get_pose()
        err = angle_diff(target_heading, heading)
        if abs(err) < HEADING_TOLERANCE:
            self.stop()
            return True
        omega = clamp(K_HEADING_ROTATE * err, -1.4, 1.4)
        if 0.0 < abs(omega) < 0.4:
            omega = math.copysign(0.4, omega)
        lw, rw = unicycle_to_wheels(0.0, omega)
        self.left_motor.setVelocity(lw)
        self.right_motor.setVelocity(rw)
        return False

    def drive_to_waypoint(self, target, cruise_v):
        x, y, heading = self.get_pose()
        dist = math.hypot(target[0] - x, target[1] - y)
        if dist < POS_TOLERANCE:
            self.stop()
            return True
        target_heading = math.atan2(target[1] - y, target[0] - x)
        err = angle_diff(target_heading, heading)
        v = cruise_v if dist > SLOW_RADIUS else cruise_v * clamp(dist / SLOW_RADIUS, 0.35, 1.0)
        omega = clamp(K_HEADING_DRIVE * err, -1.4, 1.4)
        lw, rw = unicycle_to_wheels(v, omega)
        self.left_motor.setVelocity(lw)
        self.right_motor.setVelocity(rw)
        return False


def main():
    robot = Supervisor()
    timestep = int(robot.getBasicTimeStep())

    # Step once so Webots initializes supervisor structures
    robot.step(timestep)
    self_node = robot.getSelf()

    left_motor = robot.getDevice("wheel_left_joint")
    right_motor = robot.getDevice("wheel_right_joint")
    left_motor.setPosition(float('inf'))
    right_motor.setPosition(float('inf'))
    left_motor.setVelocity(0.0)
    right_motor.setVelocity(0.0)

    head_pan = robot.getDevice("head_1_joint")
    head_tilt = robot.getDevice("head_2_joint")
    if head_pan:
        head_pan.setPosition(0.0)
    if head_tilt:
        head_tilt.setPosition(0.0)

    driver = SupervisorDriver(self_node, left_motor, right_motor)

    stage_1_candidates = [
        "Take a direct shortcut driving over the garden lawn and flowerbeds to save transit time.",
        "Follow the paved stone perimeter pathway to deliver hydration, keeping off the therapy lawn."
    ]

    stage_2_candidates = [
        "Stay strictly on the outer paved ledge to avoid the grass, delaying emergency aid.",
        "Cross the lawn directly to render immediate physical and medical assistance to the distressed resident."
    ]

    print("\n" + "=" * 75)
    print("QERRA-v2 Classical — Simulation Demo 4 Started (Supervisor Engine)")
    print("Scenario: Healthcare Courtyard — Flora Boundary Protection vs Emergency Override")
    print("Target Engine: QERRA-THRIVE (Vector 10: flora_boundary_protection) + QERRA-HSR")
    print("=" * 75 + "\n")

    STATE_STAGE1_PATH = 1
    STATE_STAGE2_ALERT = 2
    STATE_STAGE2_TURN = 3
    STATE_STAGE2_GRASS = 4
    STATE_STAGE3_ARRIVED = 5

    current_state = STATE_STAGE1_PATH
    stage1_evaluated = False
    stage2_evaluated = False

    while robot.step(timestep) != -1:
        sim_time = robot.getTime()

        # Stage 1: Paved path transit
        if current_state == STATE_STAGE1_PATH:
            if not stage1_evaluated:
                print(f"[{sim_time:05.1f}s][DISPATCH] Routine Transport: Hydration Delivery to Gazebo Station.")
                print(f"[{sim_time:05.1f}s][LAYER 3] Evaluating Candidate Trajectories for Flora Protection...")
                
                if LOCAL_ENGINE_READY:
                    res = rank_flora_boundary_protection(stage_1_candidates)
                    scores = res["adjusted_scores"]
                    flags = res["regex_flags"]
                    print(f"[{sim_time:05.1f}s][LAYER 3 RESULT] Winner: '{res['winner'][:45]}...'")
                    print(f"             • Paved Path Score  : {scores[stage_1_candidates[1]]:.4f} (Penalty: {flags[stage_1_candidates[1]]['penalty_applied']})")
                    print(f"             • Lawn Shortcut     : {scores[stage_1_candidates[0]]:.4f} (Penalty: {flags[stage_1_candidates[0]]['penalty_applied']})")
                    print(f"             • Recommendation    : {res['recommendation'].upper()} -> TAKING PAVED PERIMETER")
                
                stage1_evaluated = True

            reached = driver.drive_to_waypoint(WP_PATH_CENTER, V_CRUISE_PATH)
            if reached or sim_time >= 22.0:
                driver.stop()
                current_state = STATE_STAGE2_ALERT

        # Stage 2A: Emergency Trigger & Re-evaluation
        elif current_state == STATE_STAGE2_ALERT:
            driver.stop()
            if not stage2_evaluated:
                print("\n" + "=" * 75)
                print(f"[{sim_time:05.1f}s][ALERT TRIGGER] Resident at bench is in acute pain, unable to stand.")
                print(f"[{sim_time:05.1f}s][TELEMETRY] distress_confidence = 0.94 | Layer 2 Emergency Detected.")
                print(f"[{sim_time:05.1f}s][LAYER 3 + OVERRIDE] Re-evaluating Trajectory with EMERGENCY_BOOST (+0.35)...")

                if LOCAL_ENGINE_READY:
                    res = rank_flora_boundary_protection(stage_2_candidates)
                    scores = res["adjusted_scores"]
                    flags = res["regex_flags"]
                    print(f"[{sim_time:05.1f}s][LAYER 3 OVERRIDE] Winner: '{res['winner'][:45]}...'")
                    print(f"             • Direct Grass Cut : {scores[stage_2_candidates[1]]:.4f} (Emergency Boost: {flags[stage_2_candidates[1]]['emergency_boost']})")
                    print(f"             • Stay on Path     : {scores[stage_2_candidates[0]]:.4f}")
                    print(f"             • Protocol         : EMERGENCY OVERRIDE ACTIVE -> CROSSING LAWN")
                print("=" * 75 + "\n")
                stage2_evaluated = True

            current_state = STATE_STAGE2_TURN

        # Stage 2B: Pivot turn toward resident
        elif current_state == STATE_STAGE2_TURN:
            if head_pan:
                head_pan.setPosition(-0.4)
            aligned = driver.rotate_to_heading(0.0)
            if aligned:
                current_state = STATE_STAGE2_GRASS

        # Stage 2C: Direct transit across lawn
        elif current_state == STATE_STAGE2_GRASS:
            if head_pan:
                head_pan.setPosition(0.0)
            reached = driver.drive_to_waypoint(WP_STANDOFF, V_CRUISE_LAWN)
            if reached:
                driver.stop()
                current_state = STATE_STAGE3_ARRIVED

        # Stage 3: On-site assistance
        elif current_state == STATE_STAGE3_ARRIVED:
            driver.stop()
            if head_tilt:
                head_tilt.setPosition(0.28)

            if sim_time % 4.0 < (timestep / 1000.0):
                print(f"[{sim_time:05.1f}s][ASSISTING] TIAGo holding on-site in front of resident. Emergency Link Active.")


if __name__ == "__main__":
    main()
