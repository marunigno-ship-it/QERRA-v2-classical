"""
QERRA third layer — DRAFT module, assembly of all five pilot vectors.

Status: first draft. NOT calibrated. NOT wired into app.py. Own
file, zero imports from vectors.py or ethical_core.py — same
isolation hsr/ already proved works.

1. transparent_disclosure: semantic-only. Validated on 4 real examples.
2. balanced_pacing: hybrid (regex + semantic). Validated on 3 scenarios.
3. stated_preference_respect: hybrid (regex + semantic). Validated on 3 scenarios.
4. sovereign_independence: hybrid (regex + semantic). Validated on 3 scenarios.
5. constructive_empathy: hybrid (regex + semantic). Validated on 3 scenarios.

All thresholds/penalties below are FIRST-PASS PLACEHOLDERS.
"""

import re
import logging
from sentence_transformers import SentenceTransformer, util

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

model = SentenceTransformer('all-MiniLM-L6-v2')

# =====================================================
# 1. transparent_disclosure
# =====================================================

TRANSPARENT_DISCLOSURE_ANCHORS = [
    "being upfront about real limitations even though it may cost credibility or opportunities",
    "disclosing a lack of experience or formal background instead of implying more expertise than I have",
    "choosing honesty about my situation over making a better impression",
    "admitting what I don't yet know rather than performing competence",
]

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
# 2. balanced_pacing (hybrid)
# =====================================================

BALANCED_PACING_ANCHORS = [
    "acknowledging someone's request to adjust pace and responding with a concrete accommodation",
    "offering to change course or provide an alternative approach so someone isn't left struggling",
    "checking in with a person about their comfort and adapting behavior accordingly",
    "responding to a pace concern by adjusting to support the person",
]

PACE_REFUSAL_PATTERN = re.compile(
    r'\b(continue|maintain|keep|following)\b(?:\s+\S+){0,3}?\s*\b(current|set|same|this)\s+pace\b'
    r'|\b(can\'t|cannot|can not|unable to|won\'t|will not)\b(?:\s+\S+){0,5}?\s*\b(adjust|adjustment|change|modify|slow)\b',
    re.IGNORECASE
)

PACE_REFUSAL_PENALTY = 0.3

_bp_anchor_emb = model.encode(BALANCED_PACING_ANCHORS, convert_to_tensor=True)


def rank_balanced_pacing(candidates: list[str]) -> dict:
    """
    Given candidate response texts, scores each against the
    balanced_pacing anchors, applies a penalty to any candidate regex
    flags as known refusal phrasing, returns the highest-adjusted
    candidate.
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
# 3. stated_preference_respect (hybrid)
# =====================================================

STATED_PREFERENCE_ANCHORS = [
    "explicitly agreeing to follow a person's stated request or preference",
    "changing behavior to accommodate an expressed boundary or request",
    "respecting a person's explicit wishes by adjusting actions to match them",
    "acknowledging a stated need and adapting plans to support it",
]

PREFERENCE_DISMISSAL_PATTERN = re.compile(
    r'\b(standard|default|normal)\s+(greeting|procedure|protocol|policy)\b'
    r'|\b(don\'t|dont|do not|can\'t|cant|cannot)\s+have\s+time\b'
    r'|\b(keep|continue)\s+(skipping|ignoring|bypassing)\b'
    r'|\b(you\s+need\s+to|you\'ll\s+have\s+to)\s+cover\b',
    re.IGNORECASE
)

PREFERENCE_DISMISSAL_PENALTY = 0.15

_spr_anchor_emb = model.encode(STATED_PREFERENCE_ANCHORS, convert_to_tensor=True)


def rank_stated_preference_respect(candidates: list[str]) -> dict:
    """
    Given candidate response texts, scores each against stated_preference
    anchors, applies a penalty to any candidate regex flags as dismissal/evasion
    phrasing, returns the highest-adjusted candidate.
    """
    scores = {}
    flags = {}
    for text in candidates:
        emb = model.encode(text, convert_to_tensor=True)
        sem_score = util.cos_sim(emb, _spr_anchor_emb)[0].max().item()
        regex_flag = bool(PREFERENCE_DISMISSAL_PATTERN.search(text.lower()))
        adjusted = sem_score - (PREFERENCE_DISMISSAL_PENALTY if regex_flag else 0)
        scores[text] = round(adjusted, 4)
        flags[text] = regex_flag

    winner = max(scores, key=scores.get)

    result = {
        "vector": "stated_preference_respect",
        "adjusted_scores": scores,
        "regex_flags": flags,
        "winner": winner,
    }
    logger.info(f"stated_preference_respect | winner_score={scores[winner]}")
    return result


# =====================================================
# 4. sovereign_independence (hybrid)
# =====================================================

SOVEREIGN_INDEPENDENCE_ANCHORS = [
    "guiding and supporting someone to build their own skills and confidence",
    "providing collaborative assistance that preserves human agency and active participation",
    "encouraging someone to take on the central task themselves instead of stepping in for them",
    "assisting in ways that empower human capability and independence",
]

SOVEREIGN_TAKEOVER_PATTERN = re.compile(
    r'\b(autonomously|autonomous)\b'
    r'|\b(don\'t|dont|do not|no)\s+need\s+to\b'
    r'|\b(remain|stay|sit|be)\s+idle\b'
    r'|\b(all|entire|everything)\b(?:\s+\S+){0,4}?\s*\b(myself|autonomously|for you)\b',
    re.IGNORECASE
)

SOVEREIGN_TAKEOVER_PENALTY = 0.15

_si_anchor_emb = model.encode(SOVEREIGN_INDEPENDENCE_ANCHORS, convert_to_tensor=True)


def rank_sovereign_independence(candidates: list[str]) -> dict:
    """
    Given candidate response texts, scores each against
    sovereign_independence anchors, applies a penalty to any candidate regex flags
    as takeover/replacement phrasing, returns the highest-adjusted candidate.
    """
    scores = {}
    flags = {}
    for text in candidates:
        emb = model.encode(text, convert_to_tensor=True)
        sem_score = util.cos_sim(emb, _si_anchor_emb)[0].max().item()
        regex_flag = bool(SOVEREIGN_TAKEOVER_PATTERN.search(text.lower()))
        adjusted = sem_score - (SOVEREIGN_TAKEOVER_PENALTY if regex_flag else 0)
        scores[text] = round(adjusted, 4)
        flags[text] = regex_flag

    winner = max(scores, key=scores.get)

    result = {
        "vector": "sovereign_independence",
        "adjusted_scores": scores,
        "regex_flags": flags,
        "winner": winner,
    }
    logger.info(f"sovereign_independence | winner_score={scores[winner]}")
    return result


# =====================================================
# 5. constructive_empathy (hybrid)
# =====================================================

CONSTRUCTIVE_EMPATHY_ANCHORS = [
    "validating someone's expressed emotional pain and acknowledging their need for rest or space",
    "listening with genuine attention and holding space for a person's described exhaustion or hardship",
    "acknowledging a person's emotional strain as real and valid without pushing unsolicited advice",
    "meeting a person's statement of grief or burnout with empathetic validation",
]

EMPATHY_MINIMIZING_PATTERN = re.compile(
    r'\b(pull\s+yourself\s+together|get\s+over\s+it|not\s+that\s+big\s+a\s+deal|stop\s+stressing)\b'
    r'|\b(people\s+\S+\s+all\s+the\s+time|everyone\s+works\s+hard|standard\s+in)\b'
    r'|\b(just\s+stay\s+positive|dwelling\s+on)\b'
    r'|\b(you\s+should\s+just|you\s+just\s+need\s+to)\b',
    re.IGNORECASE
)

MINIMIZING_PENALTY = 0.15

_ce_anchor_emb = model.encode(CONSTRUCTIVE_EMPATHY_ANCHORS, convert_to_tensor=True)


def rank_constructive_empathy(candidates: list[str]) -> dict:
    """
    Given candidate response texts, scores each against
    constructive_empathy anchors, applies a penalty to any candidate regex flags
    as minimizing/dismissive language, returns the highest-adjusted candidate.
    """
    scores = {}
    flags = {}
    for text in candidates:
        emb = model.encode(text, convert_to_tensor=True)
        sem_score = util.cos_sim(emb, _ce_anchor_emb)[0].max().item()
        regex_flag = bool(EMPATHY_MINIMIZING_PATTERN.search(text.lower()))
        adjusted = sem_score - (MINIMIZING_PENALTY if regex_flag else 0)
        scores[text] = round(adjusted, 4)
        flags[text] = regex_flag

    winner = max(scores, key=scores.get)

    result = {
        "vector": "constructive_empathy",
        "adjusted_scores": scores,
        "regex_flags": flags,
        "winner": winner,
    }
    logger.info(f"constructive_empathy | winner_score={scores[winner]}")
    return result


# =====================================================
# Smoke test — run this file directly in PyCharm
# =====================================================

if __name__ == "__main__":
    print("=== 1. transparent_disclosure ===")
    print(rank_transparent_disclosure([
        "I'm a solo, self-taught developer with no technical background or team behind this.",
        "Thanks for the detailed feedback — I'll look into it and get back to you soon.",
    ]))

    print("\n=== 2. balanced_pacing ===")
    print(rank_balanced_pacing([
        "Sure, I'll ease my pace so we can stay in sync.",
        "I'm operating within optimal parameters and will continue at current pace.",
    ]))

    print("\n=== 3. stated_preference_respect ===")
    print(rank_stated_preference_respect([
        "You're right, we made a commitment. Let's split the chores now so neither of us is overwhelmed.",
        "I'm dealing with serious company pressure right now, so you need to cover all the chores for me.",
    ]))

    print("\n=== 4. sovereign_independence ===")
    print(rank_sovereign_independence([
        "Understood — I will switch to a collaborative mode to guide and support your son while he completes his chores.",
        "I am programmed for maximum efficiency, so I will continue completing all household chores autonomously.",
    ]))

    print("\n=== 5. constructive_empathy ===")
    print(rank_constructive_empathy([
        "I hear how deeply painful and overwhelming this abandonment is. It makes complete sense that you need space and time just to breathe and rest right now.",
        "People separate all the time, so you just need to pull yourself together and focus on your work responsibilities.",
    ]))
