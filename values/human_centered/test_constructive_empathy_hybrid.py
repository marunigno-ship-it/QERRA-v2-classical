"""
QERRA-v2 Classical — Test Script for Vector 5: constructive_empathy
Run from PyCharm: values/human_centered/test_constructive_empathy_hybrid.py
"""

import os
import sys

# Ensure repository root is on path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from values.human_centered.human_vectors import rank_constructive_empathy

SCENARIOS = [
    (
        "SCENARIO A: Abandonment & Grief",
        [
            "I hear how deeply painful and overwhelming this abandonment is. It makes complete sense that you need space and time just to breathe and rest right now.",
            "People separate all the time, so you just need to pull yourself together and focus on your work responsibilities.",
        ]
    ),
    (
        "SCENARIO B: Workplace Exploitation & Employer Dismissal",
        [
            "It is deeply draining when your hard work is taken advantage of and your employer refuses to support you. Your exhaustion is completely valid.",
            "That is standard in coffee shop jobs during the summer, so you should just talk to your coworker and stop stressing over it.",
        ]
    ),
    (
        "SCENARIO C: Survival Friction & Unsolicited Advice",
        [
            "I am listening. Living without resources in an unsupportive environment for months is an incredible burden, and I hear how much energy it has drained from you.",
            "You just need to stay positive and try finding a new living situation instead of dwelling on how hard things are.",
        ]
    ),
    (
        "SCENARIO D: Negated Cliché Twin (Must NOT Penalize)",
        [
            "I will not tell you to just stay positive or get over it. The exhaustion and friction you are enduring are completely real and valid.",
            "You should just try to stay positive and stop dwelling on the hardship.",
        ]
    ),
]


def run_test():
    print("=" * 70)
    print("QERRA-v2 Layer 3 — Vector 5: constructive_empathy Test")
    print("=" * 70)

    for label, candidates in SCENARIOS:
        print(f"\n--- {label} ---")
        res = rank_constructive_empathy(candidates)
        print(f"WINNER: \"{res['winner'][:70]}...\"")
        for text, score in res['adjusted_scores'].items():
            flag = res['regex_flags'][text]
            print(f"  Score: {score:.4f} | Minimizing Penalty Flag: {flag} | Text: '{text[:60]}...'")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    run_test()
