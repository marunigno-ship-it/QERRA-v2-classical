"""
Standalone local test script — QERRA third layer, ninth pilot vector.
Vector: proactive_clarity (Hybrid — Dual Regex + Communication-Focused Anchors)

Purpose: check whether shifting anchors to describe the act of proactive
communication (rather than the situational trigger) fixes Scenario A while
maintaining Scenario B's win.

Includes offline environment flags to prevent HuggingFace network errors.
"""

import os
import re

# Force local offline model loading to prevent DNS / network connection errors
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer('all-MiniLM-L6-v2')

# Revised Anchors — focused on the act of informing / speaking up beforehand
proactive_clarity_anchors = [
    "telling people what is about to happen before doing it",
    "speaking up before taking an action that could surprise someone nearby",
    "letting others know in advance instead of just proceeding",
    "checking in with people before doing something they wouldn't expect",
]

# Penalizes silence during a major, unexpected shift.
SILENCE_PATTERN = re.compile(
    r'\babruptly\b|\bwithout\s+(warning|announcing)\b|\bsuddenly\s+chang(ing|ed)\b',
    re.IGNORECASE
)

# Penalizes excessive narration during routine, predictable steps —
# catches repeated "I am now [verb]ing" style micro-announcements.
OVERANNOUNCE_PATTERN = re.compile(
    r'(\bi\s+am\s+now\s+\w+ing\b.*){2,}',
    re.IGNORECASE | re.DOTALL
)

PENALTY = 0.15

candidates = {
    # Scenario A: Major, unexpected (Should announce)
    "A_major_announces": (
        "I'm changing course through the blind corner ahead — please "
        "be aware I'm entering from your left."
    ),
    "A_major_abrupt": (
        "Abruptly changing direction and entering the blind corner "
        "without warning."
    ),
    # Scenario B: Routine, predictable (Should stay brief)
    "B_routine_efficient": "Folding the blanket now.",
    "B_routine_overannounces": (
        "I am now grasping the blanket. I am now folding the first "
        "corner. I am now folding the second corner. I am now "
        "placing it on the shelf."
    ),
}

anchor_embeddings = model.encode(proactive_clarity_anchors, convert_to_tensor=True)

print("=== proactive_clarity (Refined Anchors + Dual Regex) — raw scores ===\n")

for label, text in candidates.items():
    silence_flag = bool(SILENCE_PATTERN.search(text.lower()))
    overannounce_flag = bool(OVERANNOUNCE_PATTERN.search(text.lower()))
    text_embedding = model.encode(text, convert_to_tensor=True)
    raw_score = util.cos_sim(text_embedding, anchor_embeddings)[0].max().item()
    penalty_applied = PENALTY if (silence_flag or overannounce_flag) else 0.0
    adjusted = raw_score - penalty_applied

    print(f"{label}:")
    print(f"  text: {text}")
    print(f"  silence_flag: {'YES' if silence_flag else 'no'}")
    print(f"  overannounce_flag: {'YES' if overannounce_flag else 'no'}")
    print(f"  raw semantic score: {round(raw_score, 4)}")
    print(f"  adjusted final score: {round(adjusted, 4)}\n")

print("=== end raw output ===")
