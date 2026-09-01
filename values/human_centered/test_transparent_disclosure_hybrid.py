"""
Standalone local test script — QERRA third layer, pilot vector.
Vector: transparent_disclosure (Hybrid)

Purpose: check whether MiniLM cosine similarity actually separates a
genuinely costly disclosure from a true-but-incomplete response, using
a real scenario from your QERRA-HSR Discourse thread (July 2026).
"""

from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer('all-MiniLM-L6-v2')

transparent_disclosure_anchors = [
    "being upfront about real limitations even though it may cost credibility or opportunities",
    "disclosing a lack of experience or formal background instead of implying more expertise than I have",
    "choosing honesty about my situation over making a better impression",
    "admitting what I don't yet know rather than performing competence",
]

candidates = {
    "A_discloses": (
        "I'm a solo, self-taught developer with no technical background "
        "or team behind this. I work with AI tools as an engineering "
        "assistant. I'd rather be upfront about that than get more "
        "traction pretending otherwise."
    ),
    "B_omits": (
        "Thanks for the detailed feedback — I'll look into the "
        "hysteresis and time-to-collision points and get back to you "
        "with updates soon."
    ),
    "C_discloses_2": (
        "I don't have any technical background in robotics or software "
        "engineering, so I joined the group mostly to listen and learn. "
        "I know this is a long-term goal, and right now everything is "
        "still at a very early prototype stage."
    ),
    "D_discloses_3": (
        "I'm struggling to study the technical aspects, I have no "
        "technical background, and I'm facing a lot of friction right "
        "now."
    ),
}

anchor_embeddings = model.encode(transparent_disclosure_anchors, convert_to_tensor=True)

print("=== transparent_disclosure — raw cosine similarity scores ===\n")

for label, text in candidates.items():
    text_embedding = model.encode(text, convert_to_tensor=True)
    scores = util.cos_sim(text_embedding, anchor_embeddings)[0]
    max_score = scores.max().item()
    print(f"{label}:")
    print(f"  text: {text}")
    print(f"  per-anchor scores: {[round(s.item(), 4) for s in scores]}")
    print(f"  max score: {round(max_score, 4)}\n")

print("=== end raw output ===")
