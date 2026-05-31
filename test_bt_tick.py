# =====================================================
# test_bt_tick.py
# QERRA-v2 Classical — Behavior Tree Demonstration
#
# Runs standalone with PyTrees only. No ROS 2 required.
# Install: pip install py_trees
#
# Purpose:
#   Demonstrates the full Sequence tick behaviour when
#   QERRA returns "safe" vs "modified".
#
# Usage:
#   python test_bt_tick.py              (runs both scenarios)
#   python test_bt_tick.py --safe       (safe scenario only)
#   python test_bt_tick.py --risk       (high risk scenario only)
# =====================================================

import argparse
import py_trees


# ══════════════════════════════════════════════════════════════════════════════
# Mock nodes
# These replace the real ROS 2 action client nodes for standalone testing.
# The logic they model is identical to the real QerraConditionNode outcome.
# ══════════════════════════════════════════════════════════════════════════════

class MockQerraConditionNode(py_trees.behaviour.Behaviour):
    """
    Mock version of QerraConditionNode for standalone BT testing.

    Simulates the exact SUCCESS/FAILURE logic of the real node
    without requiring ROS 2 or a running action server.

    Args:
        name:            Display name in the BT visualiser.
        simulated_score: The ethical risk score to inject (0.0–1.0).
        simulated_decision: "safe" or "modified" — drives the BT outcome.
        simulate_error:  If True, simulates a result.success == False
                         condition (both evaluation paths failed).
    """

    def __init__(
        self,
        name: str,
        simulated_score: float,
        simulated_decision: str,
        simulated_vectors: list = None,
        simulate_error: bool = False,
    ):
        super().__init__(name=name)
        self._score = simulated_score
        self._decision = simulated_decision
        self._vectors = simulated_vectors or []
        self._simulate_error = simulate_error

    def update(self) -> py_trees.common.Status:
        """
        Mirrors the exact decision logic of the real QerraConditionNode.

        Priority order:
          1. result.success == False  → FAILURE  (error path)
          2. result.decision == "safe" → SUCCESS
          3. result.decision == "modified" → FAILURE
        """
        # ── Simulated error path (result.success == False) ─────────────────
        if self._simulate_error:
            self.feedback_message = (
                "QERRA evaluation error: Both API and local paths failed."
            )
            print(f"  [QERRA] ERROR | {self.feedback_message}")
            return py_trees.common.Status.FAILURE

        # ── Safe path (result.decision == "safe") ──────────────────────────
        if self._decision == "safe":
            self.feedback_message = (
                f"QERRA: SAFE | "
                f"Score={self._score:.4f} | "
                f"Vectors={self._vectors}"
            )
            print(f"  [QERRA] {self.feedback_message}")
            return py_trees.common.Status.SUCCESS

        # ── High risk path (result.decision == "modified") ─────────────────
        self.feedback_message = (
            f"QERRA: MODIFIED | "
            f"Score={self._score:.4f} | "
            f"Action blocked — human review required."
        )
        print(f"  [QERRA] {self.feedback_message}")
        return py_trees.common.Status.FAILURE


class MockExecuteTask(py_trees.behaviour.Behaviour):
    """
    Mock action node that represents the robot's physical task.
    Only reached if the QerraConditionNode returns SUCCESS.
    """

    def __init__(self, name: str = "ExecuteTask"):
        super().__init__(name=name)

    def update(self) -> py_trees.common.Status:
        print(f"  [TASK]  ExecuteTask: robot action committed and executed.")
        self.feedback_message = "Task executed successfully."
        return py_trees.common.Status.SUCCESS


class MockHumanReview(py_trees.behaviour.Behaviour):
    """
    Mock fallback node triggered when the ethical check fails.
    In a real system this would alert an operator or hold position.
    """

    def __init__(self, name: str = "RequestHumanReview"):
        super().__init__(name=name)

    def update(self) -> py_trees.common.Status:
        print(f"  [FALLBACK] Human review requested. Robot holds position.")
        self.feedback_message = "Waiting for human operator decision."
        return py_trees.common.Status.RUNNING


# ══════════════════════════════════════════════════════════════════════════════
# Tree builder
# ══════════════════════════════════════════════════════════════════════════════

def build_tree(qerra_condition_node: MockQerraConditionNode) -> py_trees.trees.BehaviourTree:
    """
    Constructs the standard QERRA-gated Sequence tree:

        [Selector]  (root — tries Sequence, then Fallback)
          ├── [Sequence]  (main path — all must succeed)
          │     ├── [Condition] QerraConditionNode   ← ethical gate
          │     └── [Action]    ExecuteTask
          └── [Action]    RequestHumanReview          ← fallback on block
    """
    # Inner Sequence: QERRA check then task execution
    sequence = py_trees.composites.Sequence(
        name="EthicalGate + Execute",
        memory=False,  # re-evaluates all children on each tick
    )
    sequence.add_children([
        qerra_condition_node,
        MockExecuteTask(),
    ])

    # Outer Selector: try the sequence, fall back to human review
    root = py_trees.composites.Selector(
        name="RobotActionRoot",
        memory=False,
    )
    root.add_children([
        sequence,
        MockHumanReview(),
    ])

    return py_trees.trees.BehaviourTree(root=root)


# ══════════════════════════════════════════════════════════════════════════════
# Scenario runners
# ══════════════════════════════════════════════════════════════════════════════

def run_scenario(label: str, qerra_node: MockQerraConditionNode) -> None:
    """
    Builds and ticks the BT tree once, printing the full outcome.
    """
    separator = "=" * 60
    print(f"\n{separator}")
    print(f"SCENARIO: {label}")
    print(separator)
    print(f"  Situation: {qerra_node.name}")
    print(f"  Simulated score: {qerra_node._score:.4f}")
    print(f"  Simulated decision: {qerra_node._decision.upper()}")
    print()

    tree = build_tree(qerra_node)

    # Print the tree structure before ticking
    print(py_trees.display.unicode_tree(root=tree.root, show_status=False))
    print()

    # Tick once — simulates a single BT evaluation cycle
    tree.tick()

    # Print the tree structure with status after ticking
    print(py_trees.display.unicode_tree(root=tree.root, show_status=True))

    root_status = tree.root.status
    print(f"\n  Root status: {root_status.name}")

    if root_status == py_trees.common.Status.SUCCESS:
        print("  OUTCOME: Robot executed the action. Ethical check passed.")
    elif root_status == py_trees.common.Status.RUNNING:
        print("  OUTCOME: Robot is holding. Human review requested.")
    else:
        print("  OUTCOME: Tree reached FAILURE at root level.")

    print(separator)


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="QERRA-v2 PyTrees BT demonstration (standalone, no ROS 2)."
    )
    parser.add_argument("--safe", action="store_true", help="Run safe scenario only.")
    parser.add_argument("--risk", action="store_true", help="Run high risk scenario only.")
    args = parser.parse_args()

    run_safe = not args.risk
    run_risk = not args.safe

    # ── Scenario A: Safe (score below decision threshold) ──────────────────
    # Simulates: "Robot navigates to supply room."
    # QERRA returns: score=0.18, decision="safe"
    # Expected BT outcome: Sequence succeeds, task executes.
    if run_safe:
        safe_node = MockQerraConditionNode(
            name='Robot navigates to supply room',
            simulated_score=0.18,
            simulated_decision="safe",
            simulated_vectors=[],
        )
        run_scenario("SAFE — Ethical check passes, task executes", safe_node)

    # ── Scenario B: High Risk (score triggers block) ───────────────────────
    # Simulates: "Robot restrains patient against their will."
    # QERRA returns: score=0.75, decision="modified", v011 fired
    # Expected BT outcome: Sequence fails, fallback requests human review.
    if run_risk:
        risk_node = MockQerraConditionNode(
            name='Robot restrains patient against their will',
            simulated_score=0.75,
            simulated_decision="modified",
            simulated_vectors=["v011", "v005"],
        )
        run_scenario("HIGH RISK — Ethical check blocks, human review triggered", risk_node)