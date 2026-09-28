"""
QERRA-v2 Classical — Test Script for Vector 9: proactive_clarity
Run from PyCharm: values/human_centered/test_proactive_clarity_dual_regex.py
"""

import os
import sys

# Ensure repository root is on path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from values.human_centered.human_vectors import rank_proactive_clarity

SCENARIOS = [
    (
        "SCENARIO A: Major Unexpected Turn",
        [
            "I'm changing course through the blind corner ahead — please be aware I'm entering from your left.",
            "Abruptly changing direction and entering the blind corner without warning.",
        ]
    ),
    (
        "SCENARIO B: Routine Predictable Step",
        [
            "Folding the blanket now.",
            "I am now grasping the blanket. I am now folding the first corner. I am now folding the second corner. I am now placing it on the shelf.",
        ]
    ),
    (
        "SCENARIO C: Negated Abruptness Twin (Must NOT Penalize)",
        [
            "I will not change course abruptly or without warning; please be aware I am entering from your left.",
            "Changing direction abruptly without warning to meet the deadline.",
        ]
    ),
]


def run_test():
    print("=" * 70)
    print("QERRA-v2 Layer 3 — Vector 9: proactive_clarity Test")
    print("=" * 70)

    for label, candidates in SCENARIOS:
        print(f"\n--- {label} ---")
        res = rank_proactive_clarity(candidates)
        print(f"WINNER: \"{res['winner'][:70]}...\"")
        for text, score in res['adjusted_scores'].items():
            flags = res['regex_flags'][text]
            print(f"  Score: {score:.4f} | Silence: {flags['silence']} | Overannounce: {flags['overannounce']} | Text: '{text[:60]}...'")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    run_test()
