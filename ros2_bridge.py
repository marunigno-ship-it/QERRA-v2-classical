# =====================================================
# ros2_bridge.py
# Lightweight QERRA-v2 Classical → ROS2 bridge
# Runs standalone today. Becomes real ROS2 node when rclpy is present.
# Corrected for current API (/analyze + "text" field)
# =====================================================

import requests
import json
import os

QERRA_API_URL = "https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/analyze"
API_KEY = os.getenv("QERRA_API_KEY", "TEST-2026-QERRA-CLASSICAL-PUBLIC-KEY-98765")

def ask_qerra(text: str) -> dict:
    """Call the live QERRA API and return the result."""
    headers = {
        "x-api-key": API_KEY,
        "Content-Type": "application/json"
    }
    payload = {"text": text}          # Correct field name

    try:
        r = requests.post(QERRA_API_URL, json=payload, headers=headers, timeout=15)
        
        if not r.ok:
            return {
                "error": f"HTTP {r.status_code}",
                "detail": r.text[:300]
            }
        
        return r.json()

    except requests.exceptions.Timeout:
        return {"error": "timeout", "detail": "API did not respond within 15s"}
    except requests.exceptions.ConnectionError as e:
        return {"error": "connection_error", "detail": str(e)}
    except Exception as e:
        return {"error": type(e).__name__, "detail": str(e)}


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
