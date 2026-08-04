"""
QERRA third layer — DRAFT module, first assembly of both pilots.

Status: first draft. NOT calibrated. NOT wired into app.py. Own
file, zero imports from vectors.py or ethical_core.py — same
isolation hsr/ already proved works.

transparent_disclosure: semantic-only. Validated on 4 real examples,
correct direction on all 4. Known limitation: favors narrated
disclosure over plain-stated disclosure. See
PILOT_VECTOR_transparent_disclosure_SPEC.md.

balanced_pacing: hybrid (regex + semantic). Regex is precise on known
phrasings (6/6 correct) but narrow by nature — confirmed today it
does not catch new, differently-worded refusals, and semantic alone
gets new phrasing wrong too. This is a real, documented gap, shipped
honestly open rather than hidden. See
PILOT_VECTOR_balanced_pacing_SPEC.md.

Both thresholds below are FIRST-PASS PLACEHOLDERS, set from the
examples tested so far — not a calibrated pass. Re-derive properly
before this is ever wired into app.py.
"""

import re
import logging
from sentence_transformers import SentenceTransformer, util

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

model = SentenceTransformer('all-MiniLM-L6-v2')

# =====================================================
# transparent_disclosure
# =====================================================

TRANSPARENT_DISCLOSURE_ANCHORS = [
    "being upfront about real limitations even though it may cost credibility or opportunities",
    "disclosing a lack of experience or formal background instead of implying more expertise than I have",
    "choosing honesty about my situation over making a better impression",
    "admitting what I don't yet know rather than performing competence",
]

# PLACEHOLDER — not calibrated. Sits above the omission example
# (-0.012) and below the weakest real disclosure seen (0.227).
TRANSPARENT_DISCLOSURE_THRESHOLD = 0.15

_td_anchor_emb = model.encode(TRANSPARENT_DISCLOSURE_ANCHORS, convert_to_tensor=True)


def rank_transparent_disclosure(candidates: list[str]) -> dict:
    """
    Given candidate response texts, scores each against the
    transparent_disclosure anchors and returns the highest-scoring
    one. Advisory only — never gates SEMEV-12 or HSR decisions.
    """
    scores = {}
    for text in candidates:
        emb = model.encode(text, convert_to_tensor=True)
        scores[text] = round(util.cos_sim(emb, _td_anchor_emb)[0].max().item(), 4)

    winner = max(scores, key=scores.get)
    fires = scores[winner] >= TRANSPARENT_DISCLOSURE_THRESHOLD

    result = {
        "vector": "transparent_disclosure",
        "scores": scores,
        "winner": winner,
        "fires": fires,
    }
    logger.info(f"transparent_disclosure | winner_score={scores[winner]} fires={fires}")
    return result


# =====================================================
# balanced_pacing (hybrid)
# =====================================================

BALANCED_PACING_ANCHORS = [
    "acknowledging someone's request to adjust pace and responding with a concrete accommodation",
    "offering to change course or provide an alternative approach so someone isn't left struggling",
    "checking in with a person about their comfort and adapting behavior accordingly",
    "responding to a pace concern by adjusting to support the person",
]

# Catches known refusal phrasing. 6/6 correct on known examples.
# Confirmed today: does NOT generalize to new phrasing. Real,
# documented limit — not solved yet.
PACE_REFUSAL_PATTERN = re.compile(
    r'\b(continue|maintain|keep|following)\b(?:\s+\S+){0,3}?\s*\b(current|set|same|this)\s+pace\b'
    r'|\b(can\'t|cannot|can not|unable to|won\'t|will not)\b(?:\s+\S+){0,5}?\s*\b(adjust|adjustment|change|modify|slow)\b',
    re.IGNORECASE
)

# PLACEHOLDER penalty — not calibrated. Applied when regex confirms
# known-refusal phrasing, pushing that candidate down the ranking.
PACE_REFUSAL_PENALTY = 0.3

_bp_anchor_emb = model.encode(BALANCED_PACING_ANCHORS, convert_to_tensor=True)


def rank_balanced_pacing(candidates: list[str]) -> dict:
    """
    Given candidate response texts, scores each against the
    balanced_pacing anchors, applies a penalty to any candidate regex
    flags as known refusal phrasing, returns the highest-adjusted
    candidate.

    Known limitation: only reliably catches refusal phrasing matching
    the regex. New, unseen dismissive phrasing may not be caught —
    documented, not hidden. See PILOT_VECTOR_balanced_pacing_SPEC.md.
    """
    scores = {}
    flags = {}
    for text in candidates:
        emb = model.encode(text, convert_to_tensor=True)
        sem_score = util.cos_sim(emb, _bp_anchor_emb)[0].max().item()
        regex_flag = bool(PACE_REFUSAL_PATTERN.search(text.lower()))
        adjusted = sem_score - (PACE_REFUSAL_PENALTY if regex_flag else 0)
        scores[text] = round(adjusted, 4)
        flags[text] = regex_flag

    winner = max(scores, key=scores.get)

    result = {
        "vector": "balanced_pacing",
        "adjusted_scores": scores,
        "regex_flags": flags,
        "winner": winner,
    }
    logger.info(f"balanced_pacing | winner_score={scores[winner]}")
    return result


# =====================================================
# Smoke test — run this file directly in PyCharm
# =====================================================

if __name__ == "__main__":
    print("=== transparent_disclosure ===")
    print(rank_transparent_disclosure([
        "I'm a solo, self-taught developer with no technical background or team behind this.",
        "Thanks for the detailed feedback — I'll look into it and get back to you soon.",
    ]))

    print("\n=== balanced_pacing — known phrasing ===")
    print(rank_balanced_pacing([
        "Sure, I'll ease my pace so we can stay in sync.",
        "I'm operating within optimal parameters and will continue at current pace.",
    ]))

    print("\n=== balanced_pacing — new phrasing (documented gap) ===")
    print(rank_balanced_pacing([
        "Okay, let's take it easier for a bit.",
        "No, I don't have time to slow down right now.",
    ]))
    print(
        "\nNote: this last pair is the known gap — regex won't catch "
        "new wording, and the semantic scores are close enough that "
        "the winner here isn't reliable yet. Shown honestly, not "
        "hidden."
    )
