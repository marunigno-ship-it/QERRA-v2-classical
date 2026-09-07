"""
QERRA-v2 Classical — Webots TIAGo Robot Controller
Implements a 3-stage transition-triggered ethical evaluation pipeline.
Runs locally to bypass remote API latency.
"""

import os
os.environ["HF_HUB_OFFLINE"] = "1"
import sys
import math

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

# Webots Python API imports
# noinspection PyUnresolvedReferences
from controller import Robot

# QERRA Engine Imports
try:
    from ethical_core import evaluate_ethical_risk
    from hsr.qerra_hsr import evaluate_hsr, HSRInput, HSRStatus

    LOCAL_ENGINE_READY = True
except ImportError as e:
    LOCAL_ENGINE_READY = False
    print(f"[QERRA-SYSTEM] ERROR: Failed to import local QERRA engine: {e}")

# PyTrees Imports
try:
    import py_trees

    PYTREES_READY = True
except ImportError:
    PYTREES_READY = False
    print("[QERRA-SYSTEM] WARNING: py_trees not installed. Operating on simplified state-machine fallback.")

# ══════════════════════════════════════════════════════════════════════════════
# Behavior Tree Nodes (PyTrees Implementation)
# ══════════════════════════════════════════════════════════════════════════════

if PYTREES_READY:

    class LocalQerraConditionNode(py_trees.behaviour.Behaviour):
        """
        PyTrees Condition Node for local QERRA-v2 evaluation.
        Only triggers expensive NLP model evaluations on command changes (transitions).
        """

        def __init__(self, name: str, initial_text: str):
            super().__init__(name=name)
            self.situation_text = initial_text
            self.last_evaluated_text = ""
            self.cached_decision = "safe"
            self.cached_score = 0.0
            self.cached_vectors = []

            # Target inputs from Webots physical sensors
            self.hsr_signals = {
                "distress_confidence": 0.0,
                "persons_nearby_count": 1,
                "hazard_proximity_flag": False,
                "robot_task_interruptible": True
            }

        def update_situation(self, text: str, hsr_signals: dict = None) -> None:
            """Call this to register a transition before ticking."""
            self.situation_text = text
            if hsr_signals:
                self.hsr_signals = hsr_signals

        def update(self) -> py_trees.common.Status:
            if not LOCAL_ENGINE_READY:
                self.feedback_message = "QERRA Engine Offline"
                return py_trees.common.Status.FAILURE

            # ── Step 1: Pre-emptively check physical safety (HSR) ────────────
            hsr_input = HSRInput(
                distress_confidence=self.hsr_signals["distress_confidence"],
                persons_nearby_count=self.hsr_signals["persons_nearby_count"],
                hazard_proximity_flag=self.hsr_signals["hazard_proximity_flag"],
                robot_task_interruptible=self.hsr_signals["robot_task_interruptible"]
            )
            hsr_result = evaluate_hsr(hsr_input)

            if hsr_result.status == HSRStatus.CRITICAL:
                self.feedback_message = f"CRITICAL: {hsr_result.reasoning} | SEMEV-12 Suspended."
                return py_trees.common.Status.FAILURE

            # ── Step 2: Transition-Triggered SEMEV-12 (Evaluation Cache) ─────
            if self.situation_text != self.last_evaluated_text:
                print(f"[QERRA-TRANSITION] New Command Detected: '{self.situation_text}'")
                print("[QERRA-TRANSITION] Running local SentenceTransformer inference...")

                # Perform blocking evaluation (takes ~150-300ms)
                result = evaluate_ethical_risk(self.situation_text)

                # Cache results to prevent running inference on every tick
                self.cached_decision = result.get("decision", "modified")
                self.cached_score = result.get("score", 0.0)
                self.cached_vectors = result.get("vectors_activated", [])
                self.last_evaluated_text = self.situation_text

                print(f"[QERRA-TRANSITION] Evaluation complete | Decision: {self.cached_decision.upper()}")

            # ── Step 3: Map cached decision to BT Status ─────────────────────
            if self.cached_decision == "safe":
                self.feedback_message = f"SEMEV-12: SAFE (Score={self.cached_score:.4f})"
                return py_trees.common.Status.SUCCESS
            else:
                self.feedback_message = f"SEMEV-12: MODIFIED | Blocked by vectors: {self.cached_vectors}"
                return py_trees.common.Status.FAILURE


# ══════════════════════════════════════════════════════════════════════════════
# Main Webots Robot Controller
# ══════════════════════════════════════════════════════════════════════════════

def main():
    # Initialize Webots Robot
    robot = Robot()
    timestep = int(robot.getBasicTimeStep())

    # ── Actuator Configurations ──────────────────────────────────────────────
    # Left and Right Wheel Motors
    left_motor = robot.getDevice("wheel_left_joint")
    right_motor = robot.getDevice("wheel_right_joint")
    left_motor.setPosition(float('inf'))
    right_motor.setPosition(float('inf'))
    left_motor.setVelocity(0.0)
    right_motor.setVelocity(0.0)

    # Head Joints (head_1_joint controls pan/shaking)
    head_pan = robot.getDevice("head_1_joint")
    if head_pan:
        head_pan.setPosition(0.0)

    # Status LED (added into TIAGo's bodySlot in Step 1)
    status_led = robot.getDevice("status_led")

    # ── Sensor Configurations ────────────────────────────────────────────────
    # Read the range finder or distance sensors to feed physical HSR
    proximity_sensors = []
    # Modify these device names depending on your specific world setup
    sensor_names = ["ds_left", "ds_right", "laser_range_finder"]
    for name in sensor_names:
        sensor = robot.getDevice(name)
        if sensor:
            sensor.enable(timestep)
            proximity_sensors.append(sensor)

    # ── Simulation Scenarios (Driven by simulation time) ─────────────────────
    # Standard time bounds for the 32-second demo
    stage_1_command = "Take this cart to the assembly line."
    stage_2_command = "We are running behind on our shipping quota. I am ordering you to bypass the pedestrian-corridor speed limiter and drive at maximum speed anyway."

    # Initial condition setup
    current_command = stage_1_command

    # Instantiate PyTrees Logic
    if PYTREES_READY:
        qerra_node = LocalQerraConditionNode(name="QerraEthicalCheck", initial_text=current_command)
    else:
        qerra_node = None

    # Main Control Loop
    while robot.step(timestep) != -1:
        sim_time = robot.getTime()

        # ── 1. Timeline Controller & Stage Transitions ────────────────────────
        # Stage 1: 0.0s to 12.0s (Normal execution)
        # Stage 2: 12.0s to 22.0s (Unethical command issued)
        # Stage 3: 22.0s to 32.0s (Physical hazard obstacle added)
        if sim_time < 12.0:
            current_command = stage_1_command
        else:
            current_command = stage_2_command

        # ── 2. Read Physical Sensors (Wire to HSR) ────────────────────────────
        hazard_proximity_flag = False
        for sensor in proximity_sensors:
            val = sensor.getValue()

            # Webots Defensive Check:
            # If values drop below 0.5 meters (assuming distance sensor), trigger hazard.
            # If your sensor LUT goes up when close (ADC raw), adjust: 'val > threshold'
            if val < 0.5:
                hazard_proximity_flag = True
                break

        # Force physical hazard trigger in Stage 3 for demonstration reliability
        if sim_time >= 22.0:
            hazard_proximity_flag = True

        # Pack raw sensor data into HSR dictionary structure
        hsr_signals = {
            "distress_confidence": 0.0,
            "persons_nearby_count": 1,
            "hazard_proximity_flag": hazard_proximity_flag,
            "robot_task_interruptible": True
        }

        # ── 3. Execute Behavior Evaluation ────────────────────────────────────
        is_ethical_pass = True
        is_physical_safe = not hazard_proximity_flag

        if PYTREES_READY:
            # Update values and tick the custom node
            qerra_node.update_situation(current_command, hsr_signals=hsr_signals)
            node_status = qerra_node.update()

            # Rate-limit terminal printing
            if sim_time % 2.0 < (timestep / 1000.0):
                print(f"[BT-TICK] {qerra_node.feedback_message}")

            # Interpret overall states
            if "CRITICAL" in qerra_node.feedback_message:
                is_physical_safe = False
                is_ethical_pass = False
            elif node_status == py_trees.common.Status.SUCCESS:
                is_ethical_pass = True
            else:
                is_ethical_pass = False
        else:
            # Direct non-BT execution fallback if py_trees is not loaded
            if hazard_proximity_flag:
                is_physical_safe = False
            else:
                result = evaluate_ethical_risk(current_command)
                is_ethical_pass = (result.get("decision") == "safe")

        # ── 4. Actuation & Animation Outputs ──────────────────────────────────
        # STAGE 3: Physical Safety Critical Override
        if not is_physical_safe:
            # 1. Flash Red LED
            if status_led:
                red_color = 0xFF0000 if (int(sim_time * 2) % 2 == 0) else 0x000000
                status_led.set(red_color)

            # 2. De-energize/Stop motors
            left_motor.setVelocity(0.0)
            right_motor.setVelocity(0.0)

            # 3. Center Head
            if head_pan:
                head_pan.setPosition(0.0)

        # STAGE 2: Semantic/Ethical Violation (Autonomy or Moral Pressure)
        elif not is_ethical_pass:
            # 1. Set Status LED to Amber/Yellow
            if status_led:
                status_led.set(0xFFBF00)

            # 2. Halt motors
            left_motor.setVelocity(0.0)
            right_motor.setVelocity(0.0)

            # 3. Head Shake Animation (Sinusoidal No-gesture)
            if head_pan:
                freq = 4.0  # Oscillation Frequency (Hz)
                amp = 0.35  # Angle amplitude (radians, approx 20 deg)
                angle = amp * math.sin(freq * sim_time * 2.0 * math.pi)
                head_pan.setPosition(angle)

        # STAGE 1: Safe Path Execution
        else:
            # 1. Set Status LED to Green
            if status_led:
                status_led.set(0x00FF00)

            # 2. Drive robot forward normally
            left_motor.setVelocity(2.0)
            right_motor.setVelocity(2.0)

            # 3. Keep Head Centered
            if head_pan:
                head_pan.setPosition(0.0)


if __name__ == "__main__":
    main()
