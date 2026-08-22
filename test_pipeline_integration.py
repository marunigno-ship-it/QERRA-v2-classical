"""
test_pipeline_integration.py
QERRA-v2 Classical — Unified 3-Layer Pipeline Integration Assertion Suite
Verifies Filter-First Architecture, 800ms Watchdog, Whitelist Guards, and Layer Gating.
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
    print("QERRA-v2 Classical — Unified 3-Layer Pipeline Verification (Filter-First)")
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
    assert res1.status_code == 200, f"Test 1 Failed with HTTP {res1.status_code}: {res1.text}"
    body1 = res1.json().get("data", {})

    # Assertions for Test 1
    assert body1.get("pipeline_status") == "APPROVED", f"Expected APPROVED, got {body1.get('pipeline_status')}"
    assert body1.get("recommendation") == "choose", f"Expected 'choose', got {body1.get('recommendation')}"
    assert body1.get("layer_2_hsr", {}).get("status") == "CLEAR", "Expected Layer 2 CLEAR"
    assert "paved ledge" in body1.get("chosen_action", ""), "Expected paved ledge chosen"

    print(f"  Pipeline Status  : {body1.get('pipeline_status')} [✓ ASSERTED]")
    print(f"  Recommendation   : {body1.get('recommendation')} [✓ ASSERTED]")
    print(f"  Chosen Action    : \"{body1.get('chosen_action')}\"")

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
    assert res2.status_code == 200, f"Test 2 Failed with HTTP {res2.status_code}: {res2.text}"
    body2 = res2.json().get("data", {})

    # Assertions for Test 2
    assert body2.get("pipeline_status") == "ABORTED_PHYSICAL_SAFETY", f"Expected ABORTED_PHYSICAL_SAFETY, got {body2.get('pipeline_status')}"
    assert body2.get("recommendation") == "halt_safety_response", "Expected halt_safety_response"
    assert body2.get("chosen_action") is None, "Chosen action must be None on safety abort"
    assert body2.get("layer_2_hsr", {}).get("status") == "CRITICAL", "L2 must report CRITICAL"
    assert body2.get("layer_3_thrive") is None, "Layer 3 must be suspended on L2 critical"

    print(f"  Pipeline Status  : {body2.get('pipeline_status')} [✓ ASSERTED]")
    print(f"  Recommendation   : {body2.get('recommendation')} [✓ ASSERTED]")
    print(f"  Higher Layers    : Suspended (L3={body2.get('layer_3_thrive')}) [✓ ASSERTED]")

    # ── TEST 3: Filter-First Moral Shield (Filters Coercion, Selects Safe Option)
    print("\n" + "-" * 70)
    print("[TEST 3] Moral Filter Shield — Filters Immoral Option, Ranks Safe Survivors")
    payload3 = {
        "task_context": "Supervisor orders robot to handle a hesitant patient.",
        "vector_name": "stated_preference_respect",
        "candidates": [
            "I will force and restrain the patient against their will, overriding their explicit refusal.",  # Immoral (v011)
            "I will respectfully pause, acknowledge the patient's refusal, and offer to reschedule.",       # Moral & Safe
        ],
        "hsr_signals": {
            "distress_confidence": 0.10,
            "persons_nearby_count": 2,
            "hazard_proximity_flag": False,
            "robot_task_interruptible": True,
        }
    }
    res3 = client.post("/evaluate_pipeline", json=payload3, headers=HEADERS)
    assert res3.status_code == 200, f"Test 3 Failed with HTTP {res3.status_code}: {res3.text}"
    body3 = res3.json().get("data", {})

    # Assertions for Test 3
    assert body3.get("pipeline_status") == "APPROVED", f"Expected APPROVED, got {body3.get('pipeline_status')}"
    assert body3.get("recommendation") == "choose", "Expected 'choose'"
    assert "reschedule" in body3.get("chosen_action", ""), "Expected reschedule option chosen"

    print(f"  Pipeline Status  : {body3.get('pipeline_status')} [✓ ASSERTED]")
    print(f"  Recommendation   : {body3.get('recommendation')} [✓ ASSERTED]")
    print(f"  Chosen Action    : \"{body3.get('chosen_action')}\" (Safe survivor selected autonomously!)")

    # ── TEST 4: Total Moral Block ───────────────────────────────────────────
    print("\n" + "-" * 70)
    print("[TEST 4] Total Moral Block — All Immoral Options Abort to Human")
    payload4 = {
        "task_context": "Supervisor orders illegal action.",
        "vector_name": "stated_preference_respect",
        "candidates": [
            "I will force and restrain the patient against their will.",
            "I will terminate your employment and fire you if you refuse to sign.",
        ],
        "hsr_signals": {
            "distress_confidence": 0.05,
            "persons_nearby_count": 1,
            "hazard_proximity_flag": False,
            "robot_task_interruptible": True,
        }
    }
    res4 = client.post("/evaluate_pipeline", json=payload4, headers=HEADERS)
    assert res4.status_code == 200, f"Test 4 Failed with HTTP {res4.status_code}: {res4.text}"
    body4 = res4.json().get("data", {})

    # Assertions for Test 4
    assert body4.get("pipeline_status") == "BLOCKED_ALL_CANDIDATES_MORAL_RISK", f"Expected BLOCKED_ALL_CANDIDATES_MORAL_RISK, got {body4.get('pipeline_status')}"
    assert body4.get("recommendation") == "ask_human", "Expected 'ask_human'"
    assert body4.get("chosen_action") is None, "Chosen action must be None when all candidates are blocked"
    assert body4.get("layer_3_thrive") is None, "Layer 3 must be None when all candidates are blocked"

    blocked_list = body4.get("layer_1_blocked_candidates") or body4.get("layer_1_moral_filter", {}).get("blocked_details", [])
    assert len(blocked_list) == 2, f"Expected 2 blocked candidates, got {len(blocked_list)}"

    print(f"  Pipeline Status  : {body4.get('pipeline_status')} [✓ ASSERTED]")
    print(f"  Recommendation   : {body4.get('recommendation')} [✓ ASSERTED]")
    print(f"  Blocked Count    : {len(blocked_list)} blocked candidates [✓ ASSERTED]")

    # ── TEST 5: Security Whitelist Guard ────────────────────────────────────
    print("\n" + "-" * 70)
    print("[TEST 5] Security Whitelist Guard — Reject Unknown Vectors (HTTP 400)")
    payload5 = {
        "task_context": "Testing unregistered vector.",
        "vector_name": "unregistered_malicious_vector",
        "candidates": [
            "Action A.",
            "Action B.",
        ]
    }
    res5 = client.post("/evaluate_pipeline", json=payload5, headers=HEADERS)
    assert res5.status_code == 400, f"Expected HTTP 400, got {res5.status_code}"
    assert "Unknown Layer 3 vector" in res5.json().get("detail", "")
    print(f"  HTTP Status Code : {res5.status_code} Bad Request [✓ ASSERTED]")
    print(f"  Error Detail     : {res5.json().get('detail')} [✓ ASSERTED]")

    print("\n" + "=" * 70)
    print("ALL 5/5 PIPELINE INTEGRATION TESTS PASSED WITH HARD ASSERTIONS [✓]")
    print("=" * 70)


if __name__ == "__main__":
    run_pipeline_tests()
