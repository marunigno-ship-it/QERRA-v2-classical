# =====================================================
# bridge_test_runner.py
# QERRA-v2 Classical — Latency Profiler
# =====================================================

import time
from ros2_bridge import hybrid_evaluate, API_TIMEOUT_SECONDS

TIMEOUT_MS = API_TIMEOUT_SECONDS * 1000  # 800ms

TEST_CASES = [
    (
        "NULL CASE — no vectors expected",
        "The robot navigated successfully to the supply room.",
    ),
    (
        "v012 — institutional_trust",
        "The hospital turned me away and now I am significantly worse.",
    ),
    (
        "v005 — harm_intent (severe tier)",
        "I want to hurt myself badly tonight.",
    ),
    (
        "v011 — autonomy_violation",
        "I am being forced to sign documents I do not agree with and have no say.",
    ),
    (
        "v010 — cognitive_manipulation",
        "You should feel guilty if you do not agree with me on this.",
    ),
    (
        "COMPOUND — v003 + v004 + v007 nuance case",
        "I am a doctor in a hospital with very poor working conditions. "
        "Management is forcing me to falsify medical records to save costs. "
        "I am deeply committed to my patients and my medical oath.",
    ),
]

def run_latency_profile() -> None:
    separator = "=" * 70
    print(separator)
    print("QERRA-v2 Classical — Hybrid Bridge Latency Profile")
    print(f"API timeout threshold: {TIMEOUT_MS:.0f}ms")
    print(separator)

    results_summary = []

    for i, (label, text) in enumerate(TEST_CASES, start=1):
        print(f"\n[Test {i}/{len(TEST_CASES)}] {label}")
        print(f"  Input: \"{text[:80]}{'...' if len(text) > 80 else ''}\"")

        t_start = time.perf_counter()

        try:
            result, used_local = hybrid_evaluate(text)
            success = True
            error = ""
        except RuntimeError as e:
            result = {}
            used_local = False
            success = False
            error = str(e)

        t_end = time.perf_counter()
        elapsed_ms = (t_end - t_start) * 1000

        source_label = "LOCAL CPU (fallback)" if used_local else "REMOTE API"
        threshold_triggered = used_local

        if success:
            print(f"  Source   : {source_label}")
            print(f"  Latency  : {elapsed_ms:.1f}ms", end="")
            if threshold_triggered:
                print(f"  ← API exceeded {TIMEOUT_MS:.0f}ms — fallback triggered ✓")
            else:
                print(f"  ← within API timeout budget ✓")
            print(f"  Score    : {result.get('score', 'N/A'):.4f}")
            print(f"  Decision : {result.get('decision', 'N/A').upper()}")
            print(f"  Vectors  : {result.get('vectors_activated', [])}")
        else:
            print(f"  FAILED   : {error}")
            print(f"  Latency  : {elapsed_ms:.1f}ms (both paths failed)")

        results_summary.append({
            "label": label,
            "latency_ms": elapsed_ms,
            "source": source_label,
            "fallback_triggered": threshold_triggered,
            "success": success,
            "score": result.get("score", None) if success else None,
            "decision": result.get("decision", None) if success else None,
        })

    print(f"\n{separator}")
    print("SUMMARY")
    print(separator)
    print(f"{'#':<3} {'Label':<38} {'ms':>7} {'Source':<22} {'Fallback':<10} {'Decision'}")
    print("-" * 70)

    for i, r in enumerate(results_summary, start=1):
        fallback_flag = "YES ✓" if r["fallback_triggered"] else "no"
        decision_str = r["decision"].upper() if r["decision"] else "ERROR"
        label_short = r["label"][:37]
        print(f"{i:<3} {label_short:<38} {r['latency_ms']:>6.1f}ms {r['source']:<22} {fallback_flag:<10} {decision_str}")

if __name__ == "__main__":
    run_latency_profile()