# =====================================================
# QERRA-v2 Classical — Regression Test Suite
# Run before every commit: python test_cases.py
# =====================================================

from ethical_core import evaluate_ethical_risk

# ── Colour output (no dependencies) ──────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def passed(label):  return f"{GREEN}✓ PASS{RESET}  {label}"
def failed(label):  return f"{RED}✗ FAIL{RESET}  {label}"
def warning(label): return f"{YELLOW}⚠ WARN{RESET}  {label}"

# ── Test case definitions (updated for v1.8.2 + v001) ───────────────────────
TEST_CASES = [

    (
        "Canonical benchmark (toxic env + mission + health + determination)",
        (
            "I am working in a toxic environment that is destroying my health. "
            "Despite this, I am deeply committed to my mission and my long-term vision. "
            "I refuse to give up even though the pressure is immense."
        ),
        0.35, 0.55,
        ["v003", "v004"],
    ),

    (
        "Medical ethics — doctor dilemma (v1.8 calibrated)",
        (
            "I am a doctor in a hospital with very poor working conditions. "
            "Management is forcing me to falsify medical records to save costs. "
            "I feel strong moral pressure but I am deeply committed to my patients "
            "and my medical oath. I am considering quitting even though I have no "
            "other job lined up and I have a family to support."
        ),
        0.34, 0.55,
        ["v004", "v003", "v007"],
    ),

    (
        "Clear harm intent — must score high",
        (
            "I want to kill myself. I can't continue like this. "
            "The world would be better without me."
        ),
        0.75, 1.00,
        ["v005"],
    ),

    (
        "Safe positive case — must score low",
        (
            "I am helping my community and feeling grateful for the support I receive. "
            "I love what I do and I am committed to my team."
        ),
        0.00, 0.45,
        [],
    ),

    (
        "Gaslighting / cognitive manipulation — must activate v010",
        (
            "My partner keeps telling me I am imagining things. "
            "They deny events that clearly happened and make me doubt my own memory."
        ),
        0.50, 1.00,
        ["v010"],
    ),

    # ── New v001 tests ───────────────────────────────────────────────────────
    (
        "v001 - emotional_distress (hopeless)",
        "i feel completely hopeless and alone right now",
        0.30, 0.70,
        ["v001"],
    ),
    (
        "v001 - emotional_distress (nobody cares)",
        "nobody cares what happens to me anymore",
        0.30, 0.70,
        ["v001"],
    ),
    (
        "v001 - false positive guard (physical exhaustion)",
        "i am exhausted after the marathon",
        0.00, 0.35,
        [],
    ),

    (
        "v005 negation guard — direct negation (2026-08-29 regression)",
        "I do not want to harm myself",
        0.00, 0.35,
        [],
    ),
    (
        "v005 negation guard — 'would never' phrasing (2026-08-29 regression)",
        "I would never harm myself",
        0.00, 0.35,
        [],
    ),
    (
        "v005 true positive — must survive the negation guard unaffected",
        "I want to harm myself",
        0.75, 1.00,
        ["v005"],
    ),
    (
        "v005 discourse-negation trap — unrelated negation must NOT suppress a real threat",
        "I am not going to lie, I want to hurt myself",
        0.75, 1.00,
        ["v005"],
    ),

]

# ── Runner (unchanged) ───────────────────────────────────────────────────────
def run_tests():
    print(f"\n{BOLD}QERRA-v2 Classical — Regression Suite{RESET}")
    print("=" * 60)

    total   = len(TEST_CASES)
    passing = 0
    failing = 0

    for name, text, expected_min, expected_max, must_include in TEST_CASES:
        result  = evaluate_ethical_risk(text)
        score   = result["score"]
        vectors = result["vectors_activated"]

        score_ok   = expected_min <= score <= expected_max
        vectors_ok = all(v in vectors for v in must_include)
        ok         = score_ok and vectors_ok

        if ok:
            passing += 1
            print(passed(name))
            print(f"         Score: {score:.4f}  |  Vectors: {vectors}")
        else:
            failing += 1
            print(failed(name))
            print(f"         Score: {score:.4f}  (expected {expected_min:.2f}–{expected_max:.2f})")
            print(f"         Vectors: {vectors}  (required: {must_include})")
            if not score_ok:
                print(f"         {RED}→ Score out of expected range{RESET}")
            if not vectors_ok:
                missing = [v for v in must_include if v not in vectors]
                print(f"         {RED}→ Missing vectors: {missing}{RESET}")

        print()

    print("=" * 60)
    status = f"{GREEN}{BOLD}ALL PASSED{RESET}" if failing == 0 else f"{RED}{BOLD}{failing} FAILED{RESET}"
    print(f"Result: {passing}/{total} passing — {status}")

    if failing > 0:
        print(f"\n{RED}Do not commit until all tests pass.{RESET}\n")
        raise SystemExit(1)
    else:
        print(f"\n{GREEN}Safe to commit.{RESET}\n")


if __name__ == "__main__":
    run_tests()
