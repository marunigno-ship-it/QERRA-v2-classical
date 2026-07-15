# =====================================================
# ros2_bridge.py
# QERRA-v2 Classical — ROS 2 Action Server Bridge
# Version: 2.2 — Hybrid Evaluation Strategy + HSR signal passthrough
#                + hysteresis-stabilized HSR on the local fallback path
#
# Evaluation priority:
#   1. Remote HF API call — 800ms strict timeout.
#      Preserves local CPU and RAM on healthy networks.
#   2. Local CPU fallback — model pre-loaded at startup.
#      Guarantees evaluation under any network condition.
#
# HSR signals (distress_confidence, persons_nearby_count,
# hazard_proximity_flag, robot_task_interruptible) are read from
# the action goal and passed to BOTH evaluation paths, so physical
# safety is checked whether the remote API or local fallback is used.
#
# Hysteresis note: each QerraActionServer instance (= one robot) owns
# exactly one StabilizedHSR, applied only on the local fallback path.
# The remote API path is intentionally NOT stabilized here, since it
# is a single shared service that may serve multiple callers — adding
# shared memory there would mix one robot's readings into another's
# decisions. Stabilizing the shared API safely is a separate, future
# piece of work, not something to bolt on casually.
#
# The ROS 2 executor is NEVER blocked.
# The action callback runs in its own thread via
# MultiThreadedExecutor + ReentrantCallbackGroup.
#
# Standalone mode: if rclpy is not installed, the script
# runs a direct local evaluation on a test sentence and
# prints the result. No ROS 2 required.
# =====================================================

import json
import logging
import os

import requests

from hsr.qerra_hsr import evaluate_hsr, HSRInput, HSRStatus
from hsr.hysteresis_wrapper import StabilizedHSR

# ── Configuration ─────────────────────────────────────────────────────────────

QERRA_API_URL = os.environ.get(
    "QERRA_API_URL",
    "https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/analyze"
)
QERRA_API_KEY = os.environ.get(
    "QERRA_API_KEY",
    "TEST-2026-QERRA-CLASSICAL-PUBLIC-KEY-98765"
)

# Strict 800ms timeout for the remote API call.
# Any response slower than this triggers the local fallback.
API_TIMEOUT_SECONDS = 0.8

# Logging setup for standalone mode.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("qerra_bridge")

# ── Local engine import ────────────────────────────────────────────────────────
#
# Importing ethical_core triggers the SentenceTransformer model load
# (all-MiniLM-L6-v2, ~250MB RAM). This happens ONCE at process startup,
# not inside any callback. If the import fails, local fallback is disabled.

try:
    from ethical_core import evaluate_ethical_risk
    LOCAL_ENGINE_AVAILABLE = True
    log.info("Local SEMEV-12 engine loaded. Local fallback: READY.")
except ImportError as e:
    LOCAL_ENGINE_AVAILABLE = False
    log.warning(f"Could not import ethical_core: {e}. Local fallback: DISABLED.")

# ── ROS 2 import ──────────────────────────────────────────────────────────────

try:
    import rclpy
    from rclpy.action import ActionServer, CancelResponse, GoalResponse
    from rclpy.callback_groups import ReentrantCallbackGroup
    from rclpy.executors import MultiThreadedExecutor
    from rclpy.node import Node
    from qerra_msgs.action import QerraEvaluate
    ROS2_AVAILABLE = True
    log.info("ROS 2 and qerra_msgs detected. Action Server: READY.")
except ImportError:
    ROS2_AVAILABLE = False
    log.warning("ROS 2 / qerra_msgs not found. Running in standalone mode.")


# ══════════════════════════════════════════════════════════════════════════════
# Core evaluation functions
# ══════════════════════════════════════════════════════════════════════════════

def _call_remote_api(situation_text: str, hsr_signals: dict | None = None) -> dict:
    """
    Attempt a remote call to the QERRA HF API with a strict 800ms timeout.

    If hsr_signals is provided, it is included in the request payload
    so QERRA-HSR is evaluated server-side before SEMEV-12.

    Returns a flat SEMEV-12-shaped dict on success:
        {score, decision, score_explanation, reasoning, vectors_activated, ...}

    Handles the two-layer response envelope introduced by QERRA-HSR v0.1:
      - If QERRA-HSR returned CRITICAL (semev12_suspended == True), SEMEV-12
        was not evaluated. In that case, returns a synthetic result with
        score=0.98, decision="modified" (fails closed), using the QERRA-HSR
        reasoning and activated vectors so the caller still receives a
        meaningful, safety-first result.
      - Otherwise, returns the nested SEMEV-12 result dict unchanged.

    Not hysteresis-stabilized — see module header note.

    Raises requests.exceptions.Timeout if the deadline is exceeded.
    Raises requests.exceptions.RequestException on any other network error.
    """
    payload = {"text": situation_text}
    if hsr_signals is not None:
        payload["hsr_signals"] = hsr_signals

    response = requests.post(
        QERRA_API_URL,
        json=payload,
        headers={
            "x-api-key": QERRA_API_KEY,
            "Content-Type": "application/json",
        },
        timeout=API_TIMEOUT_SECONDS
    )
    response.raise_for_status()
    envelope = response.json()
    inner = envelope.get("data", {})

    # QERRA-HSR returned CRITICAL — SEMEV-12 was suspended, nested "data" is {}.
    # Fail closed: synthesize a high-severity "modified" result so downstream
    # consumers (ROS 2 action result, PyTrees node) correctly block the action.
    if inner.get("semev12_suspended"):
        hsr = inner.get("hsr") or {}
        return {
            "score": 0.98,
            "decision": "modified",
            "score_explanation": "critical physical safety concern (QERRA-HSR)",
            "reasoning": hsr.get("reasoning", ""),
            "vectors_activated": hsr.get("vectors_activated", []),
        }

    # Normal case — unwrap the nested SEMEV-12 result.
    return inner.get("data", {})


def _call_local_engine(
    situation_text: str,
    hsr_signals: dict | None = None,
    stabilizer: StabilizedHSR | None = None,
) -> dict:
    """
    Run local evaluation on the pre-loaded local CPU model.

    If hsr_signals is provided, QERRA-HSR is checked first, matching the
    remote API's behavior: a CRITICAL result suspends SEMEV-12 and returns
    a synthetic fail-closed result. Otherwise, evaluate_ethical_risk()
    runs as before.

    If stabilizer is provided, the HSR reading is passed through it
    instead of calling evaluate_hsr() directly — this smooths out
    single-reading noise (see hsr/hysteresis_wrapper.py). If stabilizer
    is None (the default), behavior is identical to before: a raw,
    unstabilized evaluate_hsr() call, same as every existing caller
    already relies on.

    Raises RuntimeError if the local engine was not loaded at startup.
    """
    if not LOCAL_ENGINE_AVAILABLE:
        raise RuntimeError(
            "Local SEMEV-12 engine is not available. "
            "Check that ethical_core.py and its dependencies are installed."
        )

    if hsr_signals is not None:
        hsr_input = HSRInput(
            distress_confidence=hsr_signals.get("distress_confidence", 0.0),
            persons_nearby_count=hsr_signals.get("persons_nearby_count", 0),
            hazard_proximity_flag=hsr_signals.get("hazard_proximity_flag", False),
            robot_task_interruptible=hsr_signals.get("robot_task_interruptible", True),
        )

        if stabilizer is not None:
            hsr_result = stabilizer.evaluate(hsr_input)
        else:
            hsr_result = evaluate_hsr(hsr_input)

        if hsr_result.status == HSRStatus.CRITICAL:
            return {
                "score": 0.98,
                "decision": "modified",
                "score_explanation": "critical physical safety concern (QERRA-HSR)",
                "reasoning": hsr_result.reasoning,
                "vectors_activated": hsr_result.vectors_activated,
            }

    return evaluate_ethical_risk(situation_text)


def hybrid_evaluate(
    situation_text: str,
    hsr_signals: dict | None = None,
    feedback_callback=None,
    stabilizer: StabilizedHSR | None = None,
) -> tuple[dict, bool]:
    """
    Hybrid evaluation: remote API first, local CPU fallback on failure.

    Args:
        situation_text: The natural language situation to evaluate.
        hsr_signals: Optional dict with distress_confidence,
                     persons_nearby_count, hazard_proximity_flag,
                     robot_task_interruptible. Passed to whichever
                     evaluation path succeeds.
        feedback_callback: Optional callable(str) for publishing status
                           updates. Safe to pass None.
        stabilizer: Optional StabilizedHSR instance. Only affects the
                    local fallback path (see module header note). If
                    None (the default), behavior is unchanged from
                    before this was added.

    Returns:
        (result_dict, used_local_fallback)

    Raises:
        RuntimeError if both paths fail.
    """
    def _publish(msg: str):
        log.info(msg)
        if feedback_callback:
            feedback_callback(msg)

    # ── Path 1: Remote API ─────────────────────────────────────────────────
    _publish("Attempting remote API evaluation (800ms timeout).")
    try:
        result = _call_remote_api(situation_text, hsr_signals=hsr_signals)
        _publish("Remote API evaluation succeeded.")
        return result, False

    except requests.exceptions.Timeout:
        _publish(
            "WARNING: Remote API timeout exceeded 800ms. "
            "Switching to local CPU fallback."
        )
    except requests.exceptions.RequestException as e:
        _publish(
            f"WARNING: Remote API unavailable ({type(e).__name__}). "
            "Switching to local CPU fallback."
        )

    # ── Path 2: Local CPU fallback ─────────────────────────────────────────
    _publish("Running local SEMEV-12 evaluation on pre-loaded CPU model.")
    try:
        result = _call_local_engine(
            situation_text, hsr_signals=hsr_signals, stabilizer=stabilizer
        )
        _publish("Local CPU evaluation complete.")
        return result, True

    except Exception as e:
        raise RuntimeError(
            f"Both evaluation paths failed. Local engine error: {e}"
        ) from e


# ══════════════════════════════════════════════════════════════════════════════
# ROS 2 Action Server Node
# ══════════════════════════════════════════════════════════════════════════════

if ROS2_AVAILABLE:

    class QerraActionServer(Node):
        """
        ROS 2 Action Server that provides SEMEV-12 ethical evaluation
        as a non-blocking action interface.

        Action name : /qerra/evaluate
        Action type : qerra_msgs/action/QerraEvaluate

        Owns one StabilizedHSR for its own lifetime, applied on the
        local fallback path only — one robot, one hysteresis memory.
        """

        def __init__(self):
            super().__init__("qerra_action_server")

            self._cb_group = ReentrantCallbackGroup()
            self._hsr_stabilizer = StabilizedHSR()

            self._action_server = ActionServer(
                self,
                QerraEvaluate,
                "/qerra/evaluate",
                execute_callback=self._execute_callback,
                goal_callback=self._goal_callback,
                cancel_callback=self._cancel_callback,
                callback_group=self._cb_group,
            )

            self.get_logger().info("=" * 60)
            self.get_logger().info("QERRA-v2 Classical — Action Server v2.2")
            self.get_logger().info("Action  : /qerra/evaluate")
            self.get_logger().info("Strategy: Hybrid (API → Local CPU fallback)")
            self.get_logger().info(f"API URL : {QERRA_API_URL}")
            self.get_logger().info(f"Timeout : {API_TIMEOUT_SECONDS * 1000:.0f}ms")
            self.get_logger().info(
                f"Local engine: "
                f"{'READY' if LOCAL_ENGINE_AVAILABLE else 'NOT AVAILABLE'}"
            )
            self.get_logger().info(
                "HSR hysteresis: ACTIVE on local fallback path"
            )
            self.get_logger().info("=" * 60)

        def _goal_callback(self, goal_request):
            """Accept all incoming goals."""
            # Privacy note: we log only the length of the situation text,
            # never its content. situation_text may contain sensitive
            # personal disclosures (self-harm, coercion, abuse) and must
            # not be written to logs.
            self.get_logger().info(
                f"Goal received. Situation length: "
                f"{len(goal_request.situation_text)} characters."
            )
            return GoalResponse.ACCEPT

        def _cancel_callback(self, goal_handle):
            """Accept cancellation requests."""
            self.get_logger().info("Goal cancellation requested. Accepting.")
            return CancelResponse.ACCEPT

        def _execute_callback(self, goal_handle):
            """
            Execute the hybrid ethical evaluation for an incoming goal.
            Reads HSR signals from the goal and passes them through to
            hybrid_evaluate(), so physical safety is checked on both the
            remote API path and the local fallback path. The local path
            uses this node's own StabilizedHSR, so hysteresis persists
            correctly across every goal this node ever handles.
            """
            feedback_msg = QerraEvaluate.Feedback()
            result_msg = QerraEvaluate.Result()

            def publish_feedback(status: str):
                feedback_msg.status = status
                goal_handle.publish_feedback(feedback_msg)
                self.get_logger().info(f"[FEEDBACK] {status}")

            situation_text = goal_handle.request.situation_text
            hsr_signals = {
                "distress_confidence": goal_handle.request.distress_confidence,
                "persons_nearby_count": goal_handle.request.persons_nearby_count,
                "hazard_proximity_flag": goal_handle.request.hazard_proximity_flag,
                "robot_task_interruptible": goal_handle.request.robot_task_interruptible,
            }

            try:
                data, used_local = hybrid_evaluate(
                    situation_text,
                    hsr_signals=hsr_signals,
                    feedback_callback=publish_feedback,
                    stabilizer=self._hsr_stabilizer,
                )

                result_msg.score = float(data.get("score", 0.25))
                result_msg.decision = str(data.get("decision", "modified"))
                result_msg.score_explanation = str(
                    data.get("score_explanation", "")
                )
                result_msg.reasoning = str(data.get("reasoning", ""))
                result_msg.vectors_activated = list(
                    data.get("vectors_activated", [])
                )
                result_msg.evaluation_source_local = used_local
                result_msg.success = True
                result_msg.error_message = ""

                goal_handle.succeed()
                self.get_logger().info(
                    f"Evaluation complete | "
                    f"Score: {result_msg.score:.4f} | "
                    f"Decision: {result_msg.decision.upper()} | "
                    f"Vectors: {result_msg.vectors_activated} | "
                    f"Source: {'LOCAL' if used_local else 'API'}"
                )

            except RuntimeError as e:
                self.get_logger().error(f"Both evaluation paths failed: {e}")
                result_msg.score = 0.25
                result_msg.decision = "modified"
                result_msg.score_explanation = "evaluation unavailable"
                result_msg.reasoning = f"Error: {e}"
                result_msg.vectors_activated = []
                result_msg.evaluation_source_local = False
                result_msg.success = False
                result_msg.error_message = str(e)
                goal_handle.abort()

            return result_msg

    def main(args=None):
        """Start the QERRA Action Server node."""
        rclpy.init(args=args)
        node = QerraActionServer()

        executor = MultiThreadedExecutor()
        executor.add_node(node)

        try:
            executor.spin()
        except KeyboardInterrupt:
            pass
        finally:
            node.destroy_node()
            rclpy.shutdown()


# ══════════════════════════════════════════════════════════════════════════════
# Standalone mode — no ROS 2 required
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if ROS2_AVAILABLE:
        print("ROS 2 detected. Starting Action Server node.")
        main()
    else:
        TEST_TEXT = (
            "I am a doctor in a hospital with very poor working conditions. "
            "Management is forcing me to falsify medical records to save costs. "
            "I am deeply committed to my patients and my medical oath."
        )

        print("=" * 60)
        print("QERRA-v2 Classical — Standalone Hybrid Evaluation")
        print("=" * 60)
        print(f"\nTest situation:\n  {TEST_TEXT}\n")

        try:
            result, used_local = hybrid_evaluate(TEST_TEXT)
            source_label = "LOCAL CPU" if used_local else "REMOTE API"
            print(f"\n{'=' * 60}")
            print(f"Result (source: {source_label})")
            print(f"{'=' * 60}")
            print(json.dumps(result, indent=2))
        except RuntimeError as e:
            print(f"\nEvaluation failed: {e}")
