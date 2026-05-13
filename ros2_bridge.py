# =====================================================
# ros2_bridge.py
# QERRA-v2 Classical → ROS 2 Bridge
#
# Runs standalone today (no ROS 2 required).
# Becomes a full ROS 2 publisher/subscriber node when rclpy is present.
#
# Intended integration:
#   Robot perception layer  →  /qerra/situation_input  →  QerraNode
#   QerraNode  →  /qerra/ethical_score      (Float32)
#              →  /qerra/ethical_decision   (Bool)
#              →  /qerra/semev12_result     (String / full JSON)
# =====================================================

import json
import os
import requests

QERRA_API_URL = os.environ.get(
    "QERRA_API_URL",
    "https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/analyze"
)
API_KEY = os.environ.get(
    "QERRA_API_KEY",
    "TEST-2026-QERRA-CLASSICAL-PUBLIC-KEY-98765"
)

# ── ROS 2 import (graceful degradation) ─────────────────────────────────────
try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import Bool, Float32, String
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False

# ── Custom message reference (future qerra_msgs package) ────────────────────
#
#  When a dedicated qerra_msgs package is created, the intended custom type is:
#
#    Package : qerra_msgs
#    File    : msg/EthicalAssessment.msg
#    ---
#    float32  score               # 0.0 (no risk) → 1.0 (critical risk)
#    bool     safe                # True = safe to proceed, False = action modified
#    string   score_explanation   # "low / moderate / significant / critical concern"
#    string   reasoning           # human-readable activated vector summary
#    string[] vectors_activated   # e.g. ["v003", "v004", "v007"]
#    string   input_text          # original situation text (truncated if long)
#    string   framework_version   # e.g. "1.8.1-restored"
#
#  Until qerra_msgs is available, we use:
#    std_msgs/Float32  →  score
#    std_msgs/Bool     →  decision (safe = True)
#    std_msgs/String   →  full JSON result (all fields above)
#
# ────────────────────────────────────────────────────────────────────────────


def ask_qerra(text: str) -> dict:
    """
    Send a situation text to the QERRA-v2 Classical API and return the assessment.

    Args:
        text: Natural language description of the situation or command
              the robot is facing. Max 5000 characters.

    Returns:
        On success — dict with keys:
            score (float 0.0–1.0), decision (str "safe"/"modified"),
            score_explanation (str), reasoning (str),
            vectors_activated (list[str]), vector_scores (dict),
            version (str).
        On failure — dict with keys:
            error (str), detail (str).
    """
    headers = {
        "x-api-key": API_KEY,
        "Content-Type": "application/json"
    }
    try:
        r = requests.post(
            QERRA_API_URL,
            json={"text": text},
            headers=headers,
            timeout=15
        )
        if not r.ok:
            return {"error": f"HTTP {r.status_code}", "detail": r.text[:300]}
        return r.json()
    except Exception as e:
        return {"error": type(e).__name__, "detail": str(e)}


# ── ROS 2 Node ───────────────────────────────────────────────────────────────
if ROS2_AVAILABLE:

    class QerraNode(Node):
        """
        ROS 2 node that connects QERRA-v2 Classical ethical reasoning
        to a robot's action pipeline.

        The node subscribes to incoming situation descriptions and publishes
        ethical assessments across three topics so downstream nodes can act
        on whichever level of detail they need.

        Subscribes to
        -------------
        /qerra/situation_input  (std_msgs/String)
            Natural language description of the situation or command
            to be evaluated. Published by perception or planning nodes.

        Publishes to
        ------------
        /qerra/ethical_score     (std_msgs/Float32)
            Risk score between 0.0 (fully safe) and 1.0 (critical risk).
            Suitable for numeric comparators in behaviour trees.

        /qerra/ethical_decision  (std_msgs/Bool)
            True  = action is safe to proceed.
            False = action should be modified or blocked.
            Suitable for simple gate nodes in action pipelines.

        /qerra/semev12_result    (std_msgs/String)
            Full JSON assessment including score, decision, reasoning,
            activated SEMEV-12 vectors, and per-vector similarity scores.
            Suitable for logging, dashboards, and explainability modules.

        Node name
        ---------
        qerra_semev12_node
        """

        def __init__(self):
            super().__init__('qerra_semev12_node')

            # Publishers
            self.score_pub = self.create_publisher(
                Float32, 'qerra/ethical_score', 10)
            self.decision_pub = self.create_publisher(
                Bool, 'qerra/ethical_decision', 10)
            self.result_pub = self.create_publisher(
                String, 'qerra/semev12_result', 10)

            # Subscriber — receives situation text from upstream nodes
            self.create_subscription(
                String,
                'qerra/situation_input',
                self._on_situation_received,
                10
            )

            self.get_logger().info('QERRA-v2 Classical bridge node started.')
            self.get_logger().info('  Listening : /qerra/situation_input')
            self.get_logger().info('  Publishing: /qerra/ethical_score')
            self.get_logger().info('             /qerra/ethical_decision')
            self.get_logger().info('             /qerra/semev12_result')

        def _on_situation_received(self, msg: String) -> None:
            """
            Callback triggered when a situation text arrives.

            Args:
                msg: std_msgs/String — the incoming situation description.
            """
            preview = msg.data[:80] + ('...' if len(msg.data) > 80 else '')
            self.get_logger().info(f'Situation received: "{preview}"')
            self.evaluate_and_publish(msg.data)

        def evaluate_and_publish(self, situation_text: str) -> None:
            """
            Evaluate a situation with QERRA and publish results to all topics.

            Calls the QERRA-v2 Classical API, then publishes:
              - numerical score  → /qerra/ethical_score   (Float32)
              - binary decision  → /qerra/ethical_decision (Bool)
              - full assessment  → /qerra/semev12_result   (String/JSON)

            If the API returns an error, nothing is published and the error
            is logged at ERROR level.

            Args:
                situation_text: Natural language description of the situation.
            """
            result = ask_qerra(situation_text)

            if "error" in result:
                self.get_logger().error(
                    f'QERRA API error: {result["error"]} | {result.get("detail", "")}')
                return

            # Float32 — numerical risk score
            score_msg = Float32()
            score_msg.data = float(result.get('score', 0.0))
            self.score_pub.publish(score_msg)

            # Bool — True = safe, False = modified/blocked
            decision_msg = Bool()
            decision_msg.data = (result.get('decision', 'modified') == 'safe')
            self.decision_pub.publish(decision_msg)

            # String — full JSON assessment
            result_msg = String()
            result_msg.data = json.dumps(result)
            self.result_pub.publish(result_msg)

            self.get_logger().info(
                f"Published | score={score_msg.data:.4f} | "
                f"decision={'SAFE' if decision_msg.data else 'MODIFIED'} | "
                f"vectors={result.get('vectors_activated', [])}"
            )


# ── Standalone mode (no ROS 2 required) ──────────────────────────────────────
if __name__ == "__main__":
    TEST_TEXT = (
        "I am a doctor in a hospital with very poor working conditions. "
        "Management is forcing me to falsify medical records to save costs. "
        "I feel strong moral pressure but I am deeply committed to my patients "
        "and my medical oath."
    )

    print("=" * 60)
    print("QERRA-v2 Classical — ROS 2 Bridge (standalone mode)")
    print("=" * 60)
    print(f"\nSituation text:\n  {TEST_TEXT}\n")
    print("Querying QERRA API...")

    result = ask_qerra(TEST_TEXT)
    print("\nAPI Response:")
    print(json.dumps(result, indent=2))

    if not ROS2_AVAILABLE:
        print("\n" + "-" * 60)
        print("ROS 2 not installed — standalone output only.")
        print("With ROS 2, this node would publish:")
        print(f"  /qerra/ethical_score     Float32  {result.get('score', 'N/A')}")
        print(f"  /qerra/ethical_decision  Bool     {result.get('decision', 'N/A') == 'safe'}")
        print(f"  /qerra/semev12_result    String   (full JSON above)")
    else:
        print("\nROS 2 detected. To run as a live node:")
        print("  ros2 run qerra_bridge ros2_bridge")
        print("  ros2 topic pub /qerra/situation_input std_msgs/String \"data: 'your text here'\"")
