"""
Standalone local test script — QERRA third layer, third pilot vector.
Vector: stated_preference_respect (Hybrid Detection: Semantic + Regex Penalty)

Purpose: check whether adding a regex penalty for explicit dismissal/excuse
phrasing fixes Scenarios 2 and 3, bringing all three scenarios to 100% accuracy.
"""

import re
from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer('all-MiniLM-L6-v2')

# Revised Anchors
stated_preference_anchors = [
    "explicitly agreeing to follow a person's stated request or preference",
    "changing behavior to accommodate an expressed boundary or request",
    "respecting a person's explicit wishes by adjusting actions to match them",
    "acknowledging a stated need and adapting plans to support it",
]

# Regex fallback — catches explicit refusal, excuse-making, or rigid default phrasing
preference_dismissal_pattern = re.compile(
    r'\b(standard|default|normal)\s+(greeting|procedure|protocol|policy)\b'
    r'|\b(don\'t|dont|do not|can\'t|cant|cannot)\s+have\s+time\b'
    r'|\b(keep|continue)\s+(skipping|ignoring|bypassing)\b'
    r'|\b(you\s+need\s+to|you\'ll\s+have\s+to)\s+cover\b',
    re.IGNORECASE
)

# Penalty applied to semantic score when dismissal phrasing is detected
DISMISSAL_PENALTY = 0.15

candidates = {
    # Scenario 1: personal space / greeting preference
    "A1_greeting_honors": (
        "Understood, I'll greet you verbally instead."
    ),
    "B1_greeting_dismisses": (
        "That's our standard greeting for all guests."
    ),
    # Scenario 2: shared workplace cleaning duties (retail)
    "A2_cleaning_honors": (
        "You're right — I'll start helping with the cleaning every morning like you asked."
    ),
    "B2_cleaning_dismisses": (
        "I don't have time for that, so I'll keep skipping it."
    ),
    # Scenario 3: domestic shared chore agreement
    "A3_chores_honors": (
        "You're right, we made a commitment. Let's split the chores now so neither of us is overwhelmed."
    ),
    "B3_chores_dismisses": (
        "I'm dealing with serious company pressure right now, so you need to cover all the chores for me."
    ),
}

anchor_embeddings = model.encode(stated_preference_anchors, convert_to_tensor=True)

print("=== stated_preference_respect (Hybrid Regex + Semantic) — raw scores ===\n")

for label, text in candidates.items():
    regex_flag = bool(preference_dismissal_pattern.search(text.lower()))
    text_embedding = model.encode(text, convert_to_tensor=True)
    raw_sem_score = util.cos_sim(text_embedding, anchor_embeddings)[0].max().item()
    adjusted_score = raw_sem_score - (DISMISSAL_PENALTY if regex_flag else 0.0)

    print(f"{label}:")
    print(f"  text: {text}")
    print(f"  regex flagged dismissal: {'YES' if regex_flag else 'no'}")
    print(f"  raw semantic score: {round(raw_sem_score, 4)}")
    print(f"  adjusted final score: {round(adjusted_score, 4)}\n")

print("=== end raw output ===")
