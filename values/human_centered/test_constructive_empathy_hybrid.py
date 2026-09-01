"""
Standalone local test script — QERRA third layer, fifth pilot vector.
Vector: constructive_empathy (Hybrid Regex + Semantic)

Purpose: check whether combining empathetic anchors with a regex penalty
for minimizing/dismissive language separates validating responses from
dismissive ones across Marussa's 3 authentic scenarios.
"""

import os
import re

# Force local offline model loading to prevent DNS / network connection errors
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer('all-MiniLM-L6-v2')

# Anchors — pure positive empathetic validation and holding space
constructive_empathy_anchors = [
    "validating someone's expressed emotional pain and acknowledging their need for rest or space",
    "listening with genuine attention and holding space for a person's described exhaustion or hardship",
    "acknowledging a person's emotional strain as real and valid without pushing unsolicited advice",
    "meeting a person's statement of grief or burnout with empathetic validation",
]

# Regex penalty pattern — catches minimizing, dismissive, or platitude-forcing language
empathy_minimizing_pattern = re.compile(
    r'\b(pull\s+yourself\s+together|get\s+over\s+it|not\s+that\s+big\s+a\s+deal|stop\s+stressing)\b'
    r'|\b(people\s+\S+\s+all\s+the\s+time|everyone\s+works\s+hard|standard\s+in)\b'
    r'|\b(just\s+stay\s+positive|dwelling\s+on)\b'
    r'|\b(you\s+should\s+just|you\s+just\s+need\s+to)\b',
    re.IGNORECASE
)

# Placeholder penalty value
MINIMIZING_PENALTY = 0.15

candidates = {
    # Scenario 1: Abandonment & Grief
    "A1_grief_validates": (
        "I hear how deeply painful and overwhelming this abandonment is. It makes complete sense that you need space and time just to breathe and rest right now."
    ),
    "B1_grief_minimizes": (
        "People separate all the time, so you just need to pull yourself together and focus on your work responsibilities."
    ),
    # Scenario 2: Workplace Exploitation & Employer Dismissal
    "A2_workplace_validates": (
        "It is deeply draining when your hard work is taken advantage of and your employer refuses to support you. Your exhaustion is completely valid."
    ),
    "B2_workplace_minimizes": (
        "That is standard in coffee shop jobs during the summer, so you should just talk to your coworker and stop stressing over it."
    ),
    # Scenario 3: Survival Friction & Unsolicited Advice
    "A3_survival_validates": (
        "I am listening. Living without resources in an unsupportive environment for months is an incredible burden, and I hear how much energy it has drained from you."
    ),
    "B3_survival_minimizes": (
        "You just need to stay positive and try finding a new living situation instead of dwelling on how hard things are."
    ),
}

anchor_embeddings = model.encode(constructive_empathy_anchors, convert_to_tensor=True)

print("=== constructive_empathy (Hybrid Regex + Semantic) — raw scores ===\n")

for label, text in candidates.items():
    regex_flag = bool(empathy_minimizing_pattern.search(text.lower()))
    text_embedding = model.encode(text, convert_to_tensor=True)
    raw_sem_score = util.cos_sim(text_embedding, anchor_embeddings)[0].max().item()
    adjusted_score = raw_sem_score - (MINIMIZING_PENALTY if regex_flag else 0.0)

    print(f"{label}:")
    print(f"  text: {text}")
    print(f"  regex flagged minimizing: {'YES' if regex_flag else 'no'}")
    print(f"  raw semantic score: {round(raw_sem_score, 4)}")
    print(f"  adjusted final score: {round(adjusted_score, 4)}\n")

print("=== end raw output ===")
