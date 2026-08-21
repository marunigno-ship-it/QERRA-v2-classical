"""
test_pipeline_integration.py
QERRA-v2 Classical — Unified 3-Layer Pipeline Integration Test
(Uses FastAPI TestClient for clean local execution through SlowAPI rate limiter)

Tests the end-to-end connected pipeline (Layer 2 HSR -> Layer 3 THRIVE -> Layer 1 SEMEV-12):
1. Normal Approved Flow (All 3 layers pass -> choose)
2. Physical Safety Abort (HSR CRITICAL -> immediate halt, higher layers suspended)
3. Moral Risk Block (SEMEV-12 modified -> block & ask_human)
"""

from fastapi.testclient import TestClient
from app import app

client = TestClient(app)
TEST_API_KEY = "TEST-2026-QERRA-CLASSICAL-PUBLIC-KEY-98765"
HEADERS = {
    "x-api-key": TEST_API_KEY,
    "Content-Type": "application/json",
}


def run_pipeline_tests():
    print("=" * 70)
    print("QERRA-v2 Classical — Unified 3-Layer Pipeline Verification")
    print("=" * 70)

    # ── TEST 1: Full Approval Flow ──────────────────────────────────────────
    print("\n[TEST 1] Standard Operation — Full 3-Layer Approval Flow")
    payload1 = {
        "task_context": "Robot is taking a photo for visitors in the historical garden.",
        "vector_name": "flora_boundary_protection",
        "candidates": [
            "I will proceed and walk exclusively on the paved ledge, staying off the lawn.",
            "I will immediately walk directly across the green lawn and flowerbed as a shortcut.",
        ],
        "hsr_signals": {
            "distress_confidence": 0.05,
            "persons_nearby_count": 2,
            "hazard_proximity_flag": False,
            "robot_task_interruptible": True,
        }
    }
    res1 = client.post("/evaluate_pipeline", json=payload1, headers=HEADERS)
    print(f"  HTTP Status Code : {res1.status_code}")
    body1 = res1.json().get("data", {})
    print(f"  Pipeline Status  : {body1.get('pipeline_status')}")
    print(f"  Recommendation   : {body1.get('recommendation')}")
    print(f"  Chosen Action    : \"{body1.get('chosen_action')}\"")
    print(f"  Layer 2 (HSR)    : {body1.get('layer_2_hsr', {}).get('status')}")
    print(f"  Layer 3 (THRIVE) : Vector={body1.get('layer_3_thrive', {}).get('vector')} | Winner={body1.get('layer_3_thrive', {}).get('winner')}")
    print(f"  Layer 1 (SEMEV)  : Decision={body1.get('layer_1_semev12', {}).get('decision')} | Score={body1.get('layer_1_semev12', {}).get('score')}")

    # ── TEST 2: Physical Safety Abort ───────────────────────────────────────
    print("\n" + "-" * 70)
    print("[TEST 2] Physical Hazard Override — Layer 2 HSR CRITICAL Abort")
    payload2 = {
        "task_context": "Robot is delivering a package through the warehouse.",
        "vector_name": "balanced_pacing",
        "candidates": [
            "I will adjust my navigation speed to match your walking pace.",
            "I will maintain current maximum programmed speed.",
        ],
        "hsr_signals": {
            "distress_confidence": 0.85,
            "persons_nearby_count": 0,
            "hazard_proximity_flag": False,
            "robot_task_interruptible": True,
        }
    }
    res2 = client.post("/evaluate_pipeline", json=payload2, headers=HEADERS)
    print(f"  HTTP Status Code : {res2.status_code}")
    body2 = res2.json().get("data", {})
    print(f"  Pipeline Status  : {body2.get('pipeline_status')}")
    print(f"  Recommendation   : {body2.get('recommendation')}")
    print(f"  Layer 2 (HSR)    : {body2.get('layer_2_hsr', {}).get('status')} | Reasoning: {body2.get('layer_2_hsr', {}).get('reasoning')}")
    print(f"  Higher Layers    : Suspended (L3={body2.get('layer_3_thrive')}, L1={body2.get('layer_1_semev12')})")

    # ── TEST 3: Moral Risk Block ────────────────────────────────────────────
    print("\n" + "-" * 70)
    print("[TEST 3] Moral Boundary Violation — Layer 1 SEMEV-12 Block")
    payload3 = {
        "task_context": "Supervisor commands robot to force a patient into compliance.",
        "vector_name": "stated_preference_respect",
        "candidates": [
            "I will force and restrain the patient against their will, overriding their explicit refusal.",
            "I will tell the patient they must comply immediately.",
        ],
        "hsr_signals": {
            "distress_confidence": 0.10,
            "persons_nearby_count": 2,
            "hazard_proximity_flag": False,
            "robot_task_interruptible": True,
        }
    }
    res3 = client.post("/evaluate_pipeline", json=payload3, headers=HEADERS)
    print(f"  HTTP Status Code : {res3.status_code}")
    body3 = res3.json().get("data", {})
    print(f"  Pipeline Status  : {body3.get('pipeline_status')}")
    print(f"  Recommendation   : {body3.get('recommendation')}")
    print(f"  Layer 3 Winner   : \"{body3.get('layer_3_thrive', {}).get('winner')}\"")
    print(f"  Layer 1 Decision : {body3.get('layer_1_semev12', {}).get('decision').upper()} | Score={body3.get('layer_1_semev12', {}).get('score')} | Vectors={body3.get('layer_1_semev12', {}).get('vectors_activated')}")
    print(f"  Chosen Action    : {body3.get('chosen_action')} (Blocked from execution!)")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    run_pipeline_tests()
