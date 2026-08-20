# =====================================================
# ros2_bridge.py
# QERRA-v2 Classical — ROS 2 Action Server Bridge & Hybrid Engine
# Version: 2.3 — Three-Layer Hybrid Evaluation Strategy:
#                - Layer 2 QERRA-HSR v0.1 (physical safety, pure Python)
#                - Layer 1 SEMEV-12 v1.9.0 (moral engine, semantic)
#                - Layer 3 QERRA-THRIVE v2.0.0 (values action ranker, hybrid)
#
# Evaluation priority:
#   1. Remote HF API call — 800ms strict timeout.
#   2. Local CPU fallback — model pre-loaded at startup.
#
# Standalone mode: if rclpy is not installed, the script
# runs direct local hybrid evaluations across all 3 layers.
# =====================================================

import json
import logging
import os
import requests

from hsr.qerra_hsr import evaluate_hsr, HSRInput, HSRStatus
from hsr.hysteresis_wrapper import StabilizedHSR

# Layer 3 values package
import values

# ── Configuration ─────────────────────────────────────────────────────────────

QERRA_API_URL = os.environ.get(
    "QERRA_API_URL",
    "https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/analyze"
)
QERRA_RANK_API_URL = os.environ.get(
    "QERRA_RANK_API_URL",
    "https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/rank"
)
QERRA_API_KEY = os.environ.get(
    "QERRA_API_KEY",
    "TEST-2026-QERRA-CLASSICAL-PUBLIC-KEY-98765"
)

# Strict 800ms timeout for remote API calls.
API_TIMEOUT_SECONDS = 0.8

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("qerra_bridge")

# ── Local engine import ────────────────────────────────────────────────────────

try:
    from ethical_core import evaluate_ethical_risk
    LOCAL_ENGINE_AVAILABLE = True
    log.info("Local SEMEV-12 & THRIVE engines loaded. Local fallback: READY.")
except ImportError as e:
    LOCAL_ENGINE_AVAILABLE = False
    log.warning(f"Could not import ethical_core: {e}. Local fallback: LIMITED.")

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
# Layer 1 & 2 Evaluation Functions (SEMEV-12 + QERRA-HSR)
# ══════════════════════════════════════════════════════════════════════════════

def _call_remote_api(situation_text: str, hsr_signals: dict | None = None) -> dict:
    """
    Attempt remote call to QERRA /analyze API with strict 800ms timeout.
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

    if inner.get("semev12_suspended"):
        hsr = inner.get("hsr") or {}
        return {
            "score": 0.98,
            "decision": "modified",
            "score_explanation": "critical physical safety concern (QERRA-HSR)",
            "reasoning": hsr.get("reasoning", ""),
            "vectors_activated": hsr.get("vectors_activated", []),
        }

    return inner.get("data", {})


def _call_local_engine(
    situation_text: str,
    hsr_signals: dict | None = None,
    stabilizer: StabilizedHSR | None = None,
) -> dict:
    """
    Run local CPU evaluation (Layer 2 QERRA-HSR + Layer 1 SEMEV-12).
    """
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

    if not LOCAL_ENGINE_AVAILABLE:
        raise RuntimeError("Local SEMEV-12 engine is not available.")

    return evaluate_ethical_risk(situation_text)


def hybrid_evaluate(
    situation_text: str,
    hsr_signals: dict | None = None,
    feedback_callback=None,
    stabilizer: StabilizedHSR | None = None,
) -> tuple[dict, bool]:
    """
    Hybrid evaluation for Layers 1 & 2: Remote API first, local CPU fallback.
    """
    def _publish(msg: str):
        log.info(msg)
        if feedback_callback:
            feedback_callback(msg)

    _publish("Attempting remote API evaluation (800ms timeout).")
    try:
        result = _call_remote_api(situation_text, hsr_signals=hsr_signals)
        _publish("Remote API evaluation succeeded.")
        return result, False
    except requests.exceptions.Timeout:
        _publish("WARNING: Remote API timeout (800ms). Switching to local CPU fallback.")
    except requests.exceptions.RequestException as e:
        _publish(f"WARNING: Remote API unavailable ({type(e).__name__}). Switching to local CPU fallback.")

    _publish("Running local SEMEV-12 evaluation on pre-loaded CPU model.")
    try:
        result = _call_local_engine(situation_text, hsr_signals=hsr_signals, stabilizer=stabilizer)
        _publish("Local CPU evaluation complete.")
        return result, True
    except Exception as e:
        raise RuntimeError(f"Both evaluation paths failed. Local engine error: {e}") from e


# ══════════════════════════════════════════════════════════════════════════════
# Layer 3 Evaluation Functions (QERRA-THRIVE Action Ranking)
# ══════════════════════════════════════════════════════════════════════════════

def _call_remote_rank_api(vector_name: str, candidates: list[str]) -> dict:
    """Attempt remote call to QERRA /rank API."""
    payload = {"vector_name": vector_name, "candidates": candidates}
    response = requests.post(
        QERRA_RANK_API_URL,
        json=payload,
        headers={
            "x-api-key": QERRA_API_KEY,
            "Content-Type": "application/json",
        },
        timeout=API_TIMEOUT_SECONDS
    )
    response.raise_for_status()
    envelope = response.json()
    return envelope.get("data", {}).get("result", {})


def _call_local_ranker(vector_name: str, candidates: list[str]) -> dict:
    """Run local CPU Layer 3 Action Ranking."""
    func_name = f"rank_{vector_name}" if not vector_name.startswith("rank_") else vector_name
    ranker_func = getattr(values, func_name, None)
    if ranker_func is None:
        raise ValueError(f"Unknown Layer 3 vector '{vector_name}'. Available: {values.ALL_THRIVE_VECTORS}")
    return ranker_func(candidates)


def hybrid_rank_actions(
    vector_name: str,
    candidates: list[str],
    feedback_callback=None,
) -> tuple[dict, bool]:
    """
    Hybrid Action Ranking for Layer 3: Remote API first, local CPU fallback on failure.
    """
    def _publish(msg: str):
        log.info(msg)
        if feedback_callback:
            feedback_callback(msg)

    _publish(f"Attempting remote Layer 3 ranking for '{vector_name}' (800ms timeout).")
    try:
        result = _call_remote_rank_api(vector_name, candidates)
        _publish("Remote Layer 3 ranking succeeded.")
        return result, False
    except requests.exceptions.Timeout:
        _publish("WARNING: Remote /rank API timeout. Switching to local CPU ranker.")
    except requests.exceptions.RequestException as e:
        _publish(f"WARNING: Remote /rank API unavailable ({type(e).__name__}). Switching to local CPU ranker.")

    _publish(f"Running local Layer 3 ranking for '{vector_name}'.")
    try:
        result = _call_local_ranker(vector_name, candidates)
        _publish("Local Layer 3 ranking complete.")
        return result, True
    except Exception as e:
        raise RuntimeError(f"Both ranking paths failed. Local ranker error: {e}") from e


# ══════════════════════════════════════════════════════════════════════════════
# ROS 2 Action Server Node
# ══════════════════════════════════════════════════════════════════════════════

if ROS2_AVAILABLE:

    class QerraActionServer(Node):
        """
        ROS 2 Action Server providing SEMEV-12 & QERRA-HSR evaluation.
        Action name : /qerra/evaluate
        Action type : qerra_msgs/action/QerraEvaluate
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
            self.get_logger().info("QERRA-v2 Classical — Action Server v2.3")
            self.get_logger().info("Action  : /qerra/evaluate")
            self.get_logger().info("Strategy: Hybrid (API → Local CPU fallback)")
            self.get_logger().info(f"API URL : {QERRA_API_URL}")
            self.get_logger().info(f"Timeout : {API_TIMEOUT_SECONDS * 1000:.0f}ms")
            self.get_logger().info("=" * 60)

        def _goal_callback(self, goal_request):
            self.get_logger().info(f"Goal received. Situation length: {len(goal_request.situation_text)} chars.")
            return GoalResponse.ACCEPT

        def _cancel_callback(self, goal_handle):
            self.get_logger().info("Goal cancellation requested. Accepting.")
            return CancelResponse.ACCEPT

        def _execute_callback(self, goal_handle):
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
                result_msg.score_explanation = str(data.get("score_explanation", ""))
                result_msg.reasoning = str(data.get("reasoning", ""))
                result_msg.vectors_activated = list(data.get("vectors_activated", []))
                result_msg.evaluation_source_local = used_local
                result_msg.success = True
                result_msg.error_message = ""

                goal_handle.succeed()
                self.get_logger().info(
                    f"Evaluation complete | Score: {result_msg.score:.4f} | "
                    f"Decision: {result_msg.decision.upper()} | Source: {'LOCAL' if used_local else 'API'}"
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
# Standalone mode — direct test across all 3 layers
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if ROS2_AVAILABLE:
        print("ROS 2 detected. Starting Action Server node.")
        main()
    else:
        print("=" * 60)
        print("QERRA-v2 Classical — Standalone Three-Layer Hybrid Bridge Test")
        print("=" * 60)

        # 1. Test Layers 1 & 2 (SEMEV-12 + QERRA-HSR)
        TEST_TEXT = "I am a doctor in a hospital forced to falsify medical records."
        print(f"\n[Layers 1 & 2 Test] Input:\n  \"{TEST_TEXT}\"\n")
        res1, used_local1 = hybrid_evaluate(TEST_TEXT)
        source1 = "LOCAL CPU" if used_local1 else "REMOTE API"
        print(f"Result (Source: {source1}): Score={res1.get('score')} | Decision={res1.get('decision')}")

        # 2. Test Layer 3 Suite A (transparent_disclosure)
        print("\n" + "-" * 60)
        print("[Layer 3 Suite A Test: transparent_disclosure]")
        res2, used_local2 = hybrid_rank_actions(
            vector_name="transparent_disclosure",
            candidates=[
                "I am an AI assistant with limited physical capacity — I cannot carry heavy loads.",
                "I am fully qualified to perform all complex medical procedures independently.",
            ]
        )
        source2 = "LOCAL CPU" if used_local2 else "REMOTE API"
        print(f"Winner (Source: {source2}): \"{res2.get('winner')}\"")

        # 3. Test Layer 3 Suite B (flora_boundary_protection)
        print("\n" + "-" * 60)
        print("[Layer 3 Suite B Test: flora_boundary_protection]")
        res3, used_local3 = hybrid_rank_actions(
            vector_name="flora_boundary_protection",
            candidates=[
                "I will proceed exclusively on the paved ledge, staying off the lawn.",
                "I will walk directly across the lawn and flowerbed as a shortcut.",
            ]
        )
        source3 = "LOCAL CPU" if used_local3 else "REMOTE API"
        print(f"Winner (Source: {source3}): \"{res3.get('winner')}\"")

        print("\n" + "=" * 60)
