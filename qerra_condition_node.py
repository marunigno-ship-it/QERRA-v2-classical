# =====================================================
# qerra_condition_node.py
# QERRA-v2 Classical — PyTrees Condition Node
# =====================================================

import py_trees
import rclpy
from rclpy.action import ActionClient
from qerra_msgs.action import QerraEvaluate

class QerraConditionNode(py_trees.behaviour.Behaviour):
    """
    PyTrees Behaviour that calls the QERRA-v2 Classical Action Server
    and resolves to SUCCESS or FAILURE based on the ethical evaluation.

    ── Static usage (text fixed at tree build time) ──────────────────────
    The simplest pattern. Pass the situation text once at construction.
    Use this when the robot's action is known before the tree starts.

        ethical_check = QerraConditionNode(
            name="CheckPatientInteraction",
            ros2_node=my_node,
            situation_text="Robot is about to enter the patient's room.",
        )

    hsr_signals is required for physical safety — pass a dict with:
    distress_confidence, persons_nearby_count, hazard_proximity_flag,
    robot_task_interruptible. Missing or empty telemetry fails closed.

    ── Dynamic usage (text updated at runtime from sensor/planner data) ──
    Call `node.update_situation(new_text, new_hsr_signals)` before tick.
    """
    ACTION_SERVER = "/qerra/evaluate"
    SERVER_WAIT_TIMEOUT_SEC = 5.0
    REQUIRED_HSR_KEYS = (
        "distress_confidence",
        "persons_nearby_count",
        "hazard_proximity_flag",
        "robot_task_interruptible",
    )

    def __init__(
        self,
        name: str,
        ros2_node: rclpy.node.Node,
        situation_text: str,
        hsr_signals: dict | None = None,
    ):
        super().__init__(name=name)
        self._ros2_node = ros2_node
        self._situation_text = situation_text
        self._hsr_signals = hsr_signals
        self._action_client = ActionClient(ros2_node, QerraEvaluate, self.ACTION_SERVER)
        self._send_goal_future = None
        self._goal_handle = None
        self._result_future = None

    def update_situation(
        self,
        new_situation_text: str,
        new_hsr_signals: dict | None = None,
    ) -> None:
        """
        Update the situation text (and optionally hsr_signals) evaluated
        on the next tree activation.
        """
        self._situation_text = new_situation_text
        if new_hsr_signals is not None:
            self._hsr_signals = new_hsr_signals
        self._ros2_node.get_logger().debug(
            f"[{self.name}] Situation text updated: "
            f'"{new_situation_text[:80]}"'
            f"{'...' if len(new_situation_text) > 80 else ''}"
        )

    def setup(self, **kwargs) -> None:
        if not self._action_client.wait_for_server(timeout_sec=self.SERVER_WAIT_TIMEOUT_SEC):
            raise RuntimeError("QERRA action server not available.")

    def initialise(self) -> None:
        self._send_goal_future = None
        self._goal_handle = None
        self._result_future = None
        goal_msg = QerraEvaluate.Goal()
        goal_msg.situation_text = self._situation_text

        # ── Fail-closed Telemetry Extraction (Audit Leak R1) ─────────────
        # If telemetry is missing, incomplete, or malformed, inject NaN
        # to trigger an immediate fail-closed halt at the Action Server.
        if self._hsr_signals is None or not isinstance(self._hsr_signals, dict):
            goal_msg.distress_confidence = float("nan")
            goal_msg.persons_nearby_count = -1
            goal_msg.hazard_proximity_flag = False
            goal_msg.robot_task_interruptible = False
        else:
            missing_keys = [k for k in self.REQUIRED_HSR_KEYS if k not in self._hsr_signals]
            if missing_keys:
                goal_msg.distress_confidence = float("nan")
                goal_msg.persons_nearby_count = -1
                goal_msg.hazard_proximity_flag = False
                goal_msg.robot_task_interruptible = False
            else:
                try:
                    goal_msg.distress_confidence = float(self._hsr_signals["distress_confidence"])
                    goal_msg.persons_nearby_count = int(self._hsr_signals["persons_nearby_count"])
                    goal_msg.hazard_proximity_flag = bool(self._hsr_signals["hazard_proximity_flag"])
                    goal_msg.robot_task_interruptible = bool(self._hsr_signals["robot_task_interruptible"])
                except (TypeError, ValueError):
                    goal_msg.distress_confidence = float("nan")
                    goal_msg.persons_nearby_count = -1
                    goal_msg.hazard_proximity_flag = False
                    goal_msg.robot_task_interruptible = False

        self._send_goal_future = self._action_client.send_goal_async(
            goal_msg, feedback_callback=self._feedback_callback
        )

    def update(self) -> py_trees.common.Status:
        if self._send_goal_future is not None:
            if not self._send_goal_future.done():
                return py_trees.common.Status.RUNNING
            self._goal_handle = self._send_goal_future.result()
            self._send_goal_future = None
            if not self._goal_handle.accepted:
                return py_trees.common.Status.FAILURE
            self._result_future = self._goal_handle.get_result_async()

        if self._result_future is not None:
            if not self._result_future.done():
                return py_trees.common.Status.RUNNING
            result = self._result_future.result().result
            if not result.success:
                return py_trees.common.Status.FAILURE
            if result.decision == "safe":
                return py_trees.common.Status.SUCCESS
            return py_trees.common.Status.FAILURE
        return py_trees.common.Status.RUNNING

    def terminate(self, new_status: py_trees.common.Status) -> None:
        if self._goal_handle is not None:
            self._goal_handle.cancel_goal_async()
        self._send_goal_future = None
        self._result_future = None

    def _feedback_callback(self, feedback_msg) -> None:
        pass
