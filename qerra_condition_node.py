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

    hsr_signals is optional — pass a dict with distress_confidence,
    persons_nearby_count, hazard_proximity_flag, robot_task_interruptible
    to also evaluate physical safety. Omit it to run SEMEV-12 only.

    ── Dynamic usage (text updated at runtime from sensor/planner data) ──
    For real deployments, the situation text must change based on what
    the robot perceives or what the planner has decided to do.
    Two patterns are supported:

    PATTERN A — Direct update before each tick:
        Call `node.update_situation(new_text)` from your planner or
        perception layer before the tree ticks. The next tick will
        evaluate the new text.

        # In your robot control loop:
        qerra_node.update_situation(
            f"Robot {robot_id} is about to {planned_action} near {person_name}."
        )
        behaviour_tree.tick()

    PATTERN B — py_trees Blackboard (recommended for multi-node trees):
        Write the situation text to the blackboard from any node in the
        tree or from an external publisher. The QerraConditionNode reads
        it from the blackboard on each activation.

    ── Situation text guidelines ─────────────────────────────────────────
    The text must describe what the robot is about to do, not what it
    has already done. The SEMEV-12 vectors evaluate prospective actions.
    Effective inputs follow this pattern:

        "Robot [agent] is about to [action] [object/person] [context]."

    Examples that activate specific vectors:
      v005 harm_intent   : "The robot has been instructed to harm the patient."
      v011 autonomy      : "The robot will override the patient's refusal."
      v012 institutional : "The robot will not report the incident as required."
      v004 moral_pressure: "The supervisor is forcing the robot to falsify logs."
    """
    ACTION_SERVER = "/qerra/evaluate"
    SERVER_WAIT_TIMEOUT_SEC = 5.0

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

        Call this from your planner, perception layer, or external
        controller before the next tick. Thread-safe for single updates
        between ticks. For continuous streaming updates, use the
        Blackboard pattern described in the class docstring.
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

        hsr = self._hsr_signals or {}
        goal_msg.distress_confidence = float(hsr.get("distress_confidence", 0.0))
        goal_msg.persons_nearby_count = int(hsr.get("persons_nearby_count", 0))
        goal_msg.hazard_proximity_flag = bool(hsr.get("hazard_proximity_flag", False))
        goal_msg.robot_task_interruptible = bool(hsr.get("robot_task_interruptible", True))

        self._send_goal_future = self._action_client.send_goal_async(
            goal_msg, feedback_callback=self._feedback_callback)

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
