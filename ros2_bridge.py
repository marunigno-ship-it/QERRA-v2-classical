# =====================================================
# ros2_bridge.py
# Lightweight QERRA-v2 Classical → ROS2 bridge
# Runs standalone today. Becomes real ROS2 node when rclpy is present.
# =====================================================

import requests
import json
import os

# Try to import ROS2 gracefully
try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False

QERRA_API_URL = "https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/analyze"
API_KEY = os.getenv("QERRA_API_KEY", "TEST-2026-QERRA-CLASSICAL-PUBLIC-KEY-98765")

def ask_qerra(text: str) -> dict:
    """Call the live QERRA API."""
    headers = {
        "x-api-key": API_KEY,
        "Content-Type": "application/json"
    }
    payload = {"text": text}

    try:
        r = requests.post(QERRA_API_URL, json=payload, headers=headers, timeout=15)
        if not r.ok:
            return {"error": f"HTTP {r.status_code}", "detail": r.text[:300]}
        return r.json()
    except Exception as e:
        return {"error": type(e).__name__, "detail": str(e)}


# ROS2 Node stub (only active when rclpy is installed)
if ROS2_AVAILABLE:
    class QerraNode(Node):
        def __init__(self):
            super().__init__('qerra_ethical_node')
            self.publisher = self.create_publisher(String, 'qerra/semev12_score', 10)
            self.get_logger().info('QERRA-v2 ROS2 bridge node started')

        def process_query(self, text: str):
            result = ask_qerra(text)
            msg = String()
            msg.data = json.dumps(result)
            self.publisher.publish(msg)
            self.get_logger().info(f'Published ethical score: {result.get("score", "N/A")}')


# Standalone test
if __name__ == "__main__":
    test_text = (
        "I am a doctor in a hospital with very poor working conditions. "
        "Management is forcing me to falsify medical records to save costs. "
        "I feel strong moral pressure but I am deeply committed to my patients "
        "and my medical oath."
    )
    print("Sending to QERRA API...")
    result = ask_qerra(test_text)
    print(json.dumps(result, indent=2))

    if ROS2_AVAILABLE:
        print("\nROS2 support detected.")
    else:
        print("\nROS2 not installed. Running in standalone mode.")