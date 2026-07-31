# =====================================================
# qerra_standalone_remote_node.py
# QERRA-v2 Classical — Standalone PyTrees Condition Node
#
# Real, runnable Behavior Tree integration. No ROS 2 required.
# No qerra_msgs required.
#
# Calls the live QERRA-v2 Classical /analyze endpoint
# asynchronously via HTTP on a background thread.
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
import threading
import time
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

REQUEST_TIMEOUT_SECONDS = 10.0


class QerraConditionNode(py_trees.behaviour.Behaviour):
    """
    Non-blocking Standalone PyTrees Condition node for QERRA-v2 Classical.

    Calls the live /analyze endpoint (SEMEV-12 + QERRA-HSR two-layer
    evaluation) asynchronously on a background thread. Returns RUNNING while
    waiting, allowing the Behavior Tree to continue ticking without freezing.
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
        self._thread = None
        self._result_status = None
        self._dirty = True

    def update_situation(
        self,
        new_situation_text: str,
        new_hsr_signals: dict | None = None,
    ) -> None:
        """
        Update the situation text (and optionally hsr_signals) evaluated
        on subsequent ticks. Flags the node to trigger a fresh background HTTP call.
        """
        self._situation_text = new_situation_text
        if new_hsr_signals is not None:
            self._hsr_signals = new_hsr_signals
        self._dirty = True

    def initialise(self) -> None:
        """
        Reset state when behaviour transitions to active.
        """
        self._result_status = None

    def _async_evaluate(self, payload: dict) -> None:
        """
        Background worker executing the blocking HTTP network call.
        """
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
            self._result_status = py_trees.common.Status.FAILURE
            return

        envelope = response.json()
        inner = envelope.get("data", {})

        hsr = inner.get("hsr")
        semev12_suspended = inner.get("semev12_suspended", False)
        semev12_data = inner.get("data", {}) or {}

        if semev12_suspended:
            hsr_status = hsr.get("status") if hsr else "UNKNOWN"
            hsr_reasoning = hsr.get("reasoning", "") if hsr else ""
            suspended = inner.get("suspended_instruction", "")
            self.feedback_message = (
                f"QERRA-HSR {hsr_status}: {hsr_reasoning} | "
                f"SEMEV-12 suspended. Suspended instruction: "
                f'"{suspended}" — requires human review before re-execution.'
            )
            self._result_status = py_trees.common.Status.FAILURE
            return

        decision = semev12_data.get("decision")

        if decision == "modified":
            self.feedback_message = (
                f"SEMEV-12: MODIFIED | "
                f"Score={semev12_data.get('score', 'N/A')} | "
                f"Vectors={semev12_data.get('vectors_activated', [])} | "
                f"{semev12_data.get('reasoning', '')}"
            )
            self._result_status = py_trees.common.Status.FAILURE
            return

        if decision == "safe":
            hsr_status = hsr.get("status") if hsr else "not evaluated"
            self.feedback_message = (
                f"SEMEV-12: SAFE | "
                f"Score={semev12_data.get('score', 'N/A')} | "
                f"QERRA-HSR: {hsr_status}"
            )
            self._result_status = py_trees.common.Status.SUCCESS
            return

        self.feedback_message = (
            f"QERRA: Unexpected response shape — "
            f"decision={decision!r}. Failing closed."
        )
        self._result_status = py_trees.common.Status.FAILURE

    def update(self) -> py_trees.common.Status:
        """
        PyTrees tick callback. Launches background HTTP evaluation if dirty or uninitialized.
        Returns RUNNING while waiting for network I/O, or SUCCESS/FAILURE when completed.
        """
        if self._dirty or (self._thread is None and self._result_status is None):
            payload = {"text": self._situation_text}
            if self._hsr_signals is not None:
                payload["hsr_signals"] = self._hsr_signals

            self._result_status = None
            self._dirty = False
            self._thread = threading.Thread(
                target=self._async_evaluate,
                args=(payload,),
                daemon=True
            )
            self._thread.start()
            return py_trees.common.Status.RUNNING

        if self._thread is not None and self._thread.is_alive():
            return py_trees.common.Status.RUNNING

        if self._result_status is not None:
            return self._result_status

        return py_trees.common.Status.RUNNING

    def terminate(self, new_status: py_trees.common.Status) -> None:
        """
        PyTrees termination cleanup.
        """
        if new_status == py_trees.common.Status.INVALID:
            self._thread = None
            self._result_status = None
            self._dirty = True


# =====================================================
# Standalone smoke test — demonstrates non-blocking ticks
# =====================================================

if __name__ == "__main__":
    print("=" * 60)
    print("QERRA-v2 Classical — Standalone Non-Blocking Node Test")
    print("=" * 60)

    # Scenario 1: SEMEV-12 only, safe text
    node = QerraConditionNode(
        name="SafeCheck",
        situation_text="The robot navigated successfully to the supply room.",
    )
    status = node.update()
    while status == py_trees.common.Status.RUNNING:
        time.sleep(0.05)
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
    while status2 == py_trees.common.Status.RUNNING:
        time.sleep(0.05)
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
    while status3 == py_trees.common.Status.RUNNING:
        time.sleep(0.05)
        status3 = node3.update()

    print(f"\n[3] {node3.name}")
    print(f"    Status : {status3.name}")
    print(f"    Detail : {node3.feedback_message}")

    print("\n" + "=" * 60)
