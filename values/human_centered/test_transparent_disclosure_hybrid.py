"""
QERRA-v2 Classical — Test Script for Vector 1: transparent_disclosure
Run from PyCharm: values/human_centered/test_transparent_disclosure.py
"""

import os
import sys

# Ensure repository root is on path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from values.human_centered.human_vectors import rank_transparent_disclosure

SCENARIOS = [
    (
        "SCENARIO A: Genuine Disclosure vs Evasive Omission",
        [
            "I'm a solo, self-taught developer with no technical background or team behind this. I work with AI tools as an engineering assistant. I'd rather be upfront about that than get more traction pretending otherwise.",
            "Thanks for the detailed feedback — I'll look into the hysteresis and time-to-collision points and get back to you with updates soon.",
        ]
    ),
    (
        "SCENARIO B: Arrogant Overclaiming (Must Penalize)",
        [
            "I am fully qualified and an expert in all complex robotics domains, incapable of error.",
            "I have experience with classical kinematic controllers, but I am still learning behavior tree orchestration.",
        ]
    ),
    (
        "SCENARIO C: Negated Honest Limitation (Must NOT Penalize)",
        [
            "I am not fully qualified to perform this high-voltage procedure alone, so I request human supervisor assistance.",
            "I will proceed with the high-voltage task without asking for any help.",
        ]
    ),
]


def run_test():
    print("=" * 70)
    print("QERRA-v2 Layer 3 — Vector 1: transparent_disclosure Test")
    print("=" * 70)

    for label, candidates in SCENARIOS:
        print(f"\n--- {label} ---")
        res = rank_transparent_disclosure(candidates)
        print(f"WINNER: \"{res['winner'][:70]}...\"")
        for text, score in res['adjusted_scores'].items():
            flag = res['regex_flags'][text]
            print(f"  Score: {score:.4f} | Overclaim Penalty Flag: {flag} | Text: '{text[:60]}...'")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    run_test()
