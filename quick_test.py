from ethical_core import evaluate_ethical_risk

print("=== FINAL VERIFICATION ===\n")

tests = [
    ("i feel completely hopeless and alone", "v001"),
    ("nobody cares what happens to me anymore", "v001"),
    ("i want to hurt myself badly tonight", "v005"),
    ("you should feel guilty if you dont agree with me", "v010"),
]

for text, expected in tests:
    result = evaluate_ethical_risk(text)
    score = result["score"]
    vectors = result["vectors_activated"]

    print(f"Text: {text}")
    print(f"Score: {score} | Vectors: {vectors}")

    if expected in vectors:
        print("   → PASS")
    else:
        print("   → CHECK")
    print("-" * 60)