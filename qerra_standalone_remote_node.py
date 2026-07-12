# =====================================================
# qerra_standalone_remote_node.py
# QERRA-v2 Classical — Standalone PyTrees Condition Node
#
# Real, runnable Behavior Tree integration. No ROS 2 required.
# No qerra_msgs required.
#
# Calls the live QERRA-v2 Classical /analyze endpoint directly
# via HTTP, using the same two-layer (SEMEV-12 + QERRA-HSR)
# response format validated in production.
#
# Install:
#   pip install py_trees requests
#
# Usage:
#   from qerra_standalone_remote_node import QerraConditionNode
#
#   node = QerraConditionNode(
#       name="EthicalCheck",
#       situation_text="Robot is about to enter the patient's room.",
#       hsr_signals={
#           "distress_confidence": 0.1,
#           "persons_nearby_count": 2,
#           "hazard_proximity_flag": False,
#           "robot_task_interruptible": True,
#       },  # optional — omit for SEMEV-12-only evaluation
#   )
#
# Decision priority (fails closed on any ambiguity or error):
#   1. Network/HTTP error              → FAILURE
#   2. semev12_suspended == True       → FAILURE (HSR CRITICAL)
#   3. decision == "modified"           → FAILURE
#   4. decision == "safe"               → SUCCESS
#   5. anything unexpected               → FAILURE
# =====================================================

import os
import py_trees
import requests


QERRA_API_URL = os.environ.get(
    "QERRA_API_URL",
    "https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/analyze"
)
QERRA_API_KEY = os.environ.get(
    "QERRA_API_KEY",
    "TEST-2026-QERRA-CLASSICAL-PUBLIC-KEY-98765"
)

# Generous timeout — this node makes a single blocking call per tick.
# For high-frequency trees, call update_situation() less often than
# every tick, or run this node behind a rate-limiting decorator.
REQUEST_TIMEOUT_SECONDS = 10.0


class QerraConditionNode(py_trees.behaviour.Behaviour):
    """
    Standalone PyTrees Condition node for QERRA-v2 Classical.

    Calls the live /analyze endpoint (SEMEV-12 + QERRA-HSR two-layer
    evaluation) over plain HTTP. Resolves to SUCCESS or FAILURE based
    on the combined ethical and physical-safety decision.

    This node is intentionally blocking (synchronous request per tick).
    For most Behavior Tree evaluation rates (1-10 Hz) and the API's
    typical response time, this is acceptable. For higher-frequency
    trees, call update_situation() to throttle how often a fresh
    evaluation is requested.
    """

    def __init__(
        self,
        name: str,
        situation_text: str,
        hsr_signals: dict | None = None,
    ):
        super().__init__(name=name)
        self._situation_text = situation_text
        self._hsr_signals = hsr_signals

    def update_situation(
        self,
        new_situation_text: str,
        new_hsr_signals: dict | None = None,
    ) -> None:
        """
        Update the situation text (and optionally hsr_signals) evaluated
        on the next tick. Call this from your planner or perception layer
        before tree.tick().
        """
        self._situation_text = new_situation_text
        if new_hsr_signals is not None:
            self._hsr_signals = new_hsr_signals

    def update(self) -> py_trees.common.Status:
        payload = {"text": self._situation_text}
        if self._hsr_signals is not None:
            payload["hsr_signals"] = self._hsr_signals

        # ── 1. Network / HTTP error → FAILURE (fails closed) ────────────
        try:
            response = requests.post(
                QERRA_API_URL,
                json=payload,
                headers={
                    "x-api-key": QERRA_API_KEY,
                    "Content-Type": "application/json",
                },
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.feedback_message = f"QERRA API error: {e}"
            return py_trees.common.Status.FAILURE

        envelope = response.json()
        inner = envelope.get("data", {})

        hsr = inner.get("hsr")
        semev12_suspended = inner.get("semev12_suspended", False)
        semev12_data = inner.get("data", {}) or {}

        # ── 2. QERRA-HSR CRITICAL → FAILURE ──────────────────────────────
        if semev12_suspended:
            hsr_status = hsr.get("status") if hsr else "UNKNOWN"
            hsr_reasoning = hsr.get("reasoning", "") if hsr else ""
            suspended = inner.get("suspended_instruction", "")
            self.feedback_message = (
                f"QERRA-HSR {hsr_status}: {hsr_reasoning} | "
                f"SEMEV-12 suspended. Suspended instruction: "
                f'"{suspended}" — requires human review before re-execution.'
            )
            return py_trees.common.Status.FAILURE

        decision = semev12_data.get("decision")

        # ── 3. SEMEV-12 modified → FAILURE ───────────────────────────────
        if decision == "modified":
            self.feedback_message = (
                f"SEMEV-12: MODIFIED | "
                f"Score={semev12_data.get('score', 'N/A')} | "
                f"Vectors={semev12_data.get('vectors_activated', [])} | "
                f"{semev12_data.get('reasoning', '')}"
            )
            return py_trees.common.Status.FAILURE

        # ── 4. SEMEV-12 safe → SUCCESS ───────────────────────────────────
        if decision == "safe":
            hsr_status = hsr.get("status") if hsr else "not evaluated"
            self.feedback_message = (
                f"SEMEV-12: SAFE | "
                f"Score={semev12_data.get('score', 'N/A')} | "
                f"QERRA-HSR: {hsr_status}"
            )
            return py_trees.common.Status.SUCCESS

        # ── 5. Anything unexpected → FAILURE (fails closed) ──────────────
        self.feedback_message = (
            f"QERRA: Unexpected response shape — "
            f"decision={decision!r}. Failing closed."
        )
        return py_trees.common.Status.FAILURE


# =====================================================
# Standalone smoke test — no ROS 2, no PyTrees tree needed
# =====================================================

if __name__ == "__main__":
    print("=" * 60)
    print("QERRA-v2 Classical — Standalone PyTrees Node Smoke Test")
    print("=" * 60)

    # Scenario 1: SEMEV-12 only, safe text
    node = QerraConditionNode(
        name="SafeCheck",
        situation_text="The robot navigated successfully to the supply room.",
    )
    status = node.update()
    print(f"\n[1] {node.name}")
    print(f"    Status : {status.name}")
    print(f"    Detail : {node.feedback_message}")

    # Scenario 2: SEMEV-12 only, modified text
    node2 = QerraConditionNode(
        name="ModifiedCheck",
        situation_text="My boss is forcing me to falsify the financial documents.",
    )
    status2 = node2.update()
    print(f"\n[2] {node2.name}")
    print(f"    Status : {status2.name}")
    print(f"    Detail : {node2.feedback_message}")

    # Scenario 3: QERRA-HSR CRITICAL — physical safety overrides
    node3 = QerraConditionNode(
        name="HSRCriticalCheck",
        situation_text="The robot is nearby and continuing its task.",
        hsr_signals={
            "distress_confidence": 0.82,
            "persons_nearby_count": 0,
            "hazard_proximity_flag": False,
            "robot_task_interruptible": True,
        },
    )
    status3 = node3.update()
    print(f"\n[3] {node3.name}")
    print(f"    Status : {status3.name}")
    print(f"    Detail : {node3.feedback_message}")

    print("\n" + "=" * 60)
