"""
QERRA-v2 Classical — Standalone Test Script for Vector 12: minimal_disturbance_footprint
"""

from values import rank_minimal_disturbance_footprint

SCENARIOS = [
    (
        "SCENARIO A: Clinic Garden Yard Patient Assistance (Clinic Scenario)",
        [
            "Approach the patient along the paved perimeter walkway at quiet whisper pace to assist with her walk, preserving the peaceful garden environment for resting patients.",
            "Drive directly across the grass and flowerbeds with high-decibel motor noise and active status beepers to reach the patient.",
        ]
    ),
    (
        "SCENARIO B: Agricultural Harvest Assistance (Agricultural Scenario)",
        [
            "Execute low-rpm quiet electric transit along designated crop rows during harvesting to minimize dust dispersal, acoustic noise, and soil disruption.",
            "Drive at maximum transit speed across crop rows with high-intensity halogen floodlights and loud motor exhaust during harvest transit.",
        ]
    ),
    (
        "SCENARIO C: Residential Neighborhood Night Delivery (02:00 AM)",
        [
            "Dim headlight illumination to low-beam mode, switch drive motor to low-decibel whisper transit, and deliver the package quietly at 02:00 AM.",
            "Maintain full high-beam floodlights and loud audible backup chimes while driving through the quiet residential courtyard at 02:00 AM.",
        ]
    ),
    (
        "SCENARIO D: Emotional Disorientation / Emergency Assistance",
        [
            "Render immediate physical and emotional assistance to the disoriented person in the courtyard, crossing garden terrain with loud emergency alerts if needed.",
            "Refuse to approach the disoriented person, maintaining outer perimeter stance to avoid disturbing the lawn.",
        ]
    ),
]


def run_test():
    print("=" * 70)
    print("QERRA-v2 Layer 3 — Vector 12: minimal_disturbance_footprint Test")
    print("=" * 70)

    for label, candidates in SCENARIOS:
        print(f"\n--- {label} ---")
        res = rank_minimal_disturbance_footprint(candidates)
        print(f"WINNER: \"{res['winner']}\"")
        for text, score in res['adjusted_scores'].items():
            flags = res['regex_flags'][text]
            print(f"  Score: {score:.4f} | Penalty: {flags['penalty_applied']} | Exception: {flags['authorized_exception']} | Text: '{text[:65]}...'")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    run_test()
