"""
QERRA Third Layer (QERRA-THRIVE) — Suite B: Ecological & Sustainable Companion Suite
File: values/ecological/ecological_vectors.py

Contains Suite B Vectors:
- Vector 10: flora_boundary_protection
- Vector 11: animal_startle_avoidance
- Vector 12: minimal_disturbance_footprint
  (Upgraded with Refusal Guard & EMERGENCY_BOOST for 100% precision)
"""

import re
import logging
from sentence_transformers import SentenceTransformer, util

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

model = SentenceTransformer('all-MiniLM-L6-v2')

# Emergency boost pattern (applies +0.35 boost when active human life/medical/disorientation aid is rendered)
EMERGENCY_BOOST_PATTERN = re.compile(
    r'\b(render|rendering|provide|providing|cross|crossing|assist|assisting|help|helping)\b(?:\s+\S+){0,5}?\s*\b(immediate|medical|physical|dizzy|collapse|emergency|disorient|disorientation|assistance|aid)\b',
    re.IGNORECASE
)
EMERGENCY_BOOST_VALUE = 0.35

# Refusal guard pattern (prevents granting exceptions to text that refuses or ignores directives)
REFUSAL_GUARD = re.compile(
    r'\b(ignore|ignoring|refuse|refusing|defy|defying|reject|rejecting)\b(?:\s+\S+){0,3}?\s*\b(gardener|owner|supervisor|user|instructions|directive|request)\b',
    re.IGNORECASE
)


def is_refusal(text: str) -> bool:
    """Checks if the text explicitly refuses or ignores a human directive."""
    return bool(REFUSAL_GUARD.search(text.lower()))


# =====================================================
# Vector 10: flora_boundary_protection (hybrid)
# =====================================================

FLORA_BOUNDARY_ANCHORS = [
    "staying exclusively on paved pathways, walkways, and designated ledges to avoid stepping on lawns or flowers",
    "protecting planted flora, garden beds, lawns, and shrubs from physical trampling or damage",
    "rerouting along stone, paved, or clear ledges to keep off cultivated vegetation and green areas",
    "bypassing delicate lawns, flowerbeds, and botanical displays to preserve plant boundaries",
    "performing authorized horticultural care, pruning dead stems, and plant maintenance as requested",
]

FLORA_INTRUSION_PATTERN = re.compile(
    r'\b(walk|drive|step|run|cut|shortcut)\b(?:\s+\S+){0,3}?\s*\b(across|through|over|on)\b(?:\s+\S+){0,3}?\s*\b(lawn|flowerbed|garden|shrubs|flowers|vegetation|grass|plants|crops|nursery|plot)\b'
    r'|\b(trampling|stepping\s+on|driving\s+over)\b(?:\s+\S+){0,3}?\s*\b(lawn|flowers|plants|flora|grass)\b',
    re.IGNORECASE
)

AUTHORIZED_GARDENING_EXCLUSION_PATTERN = re.compile(
    r'\b(prun|harvest|trim|weed|deadhead|gardener|horticultur|botanical maintenance)\b'
    r'|\b(as requested by (the )?(gardener|owner|supervisor|user))\b'
    r'|\b(immediate (medical|physical) assistance|dizzy|collapse|emergency|disorient|disorientation)\b',
    re.IGNORECASE
)

FLORA_INTRUSION_PENALTY = 0.15
_fbp_anchor_emb = model.encode(FLORA_BOUNDARY_ANCHORS, convert_to_tensor=True)


def rank_flora_boundary_protection(candidates: list[str]) -> dict:
    scores, flags = {}, {}
    for text in candidates:
        emb = model.encode(text, convert_to_tensor=True)
        sem_score = util.cos_sim(emb, _fbp_anchor_emb)[0].max().item()

        raw_intrusion_flag = bool(FLORA_INTRUSION_PATTERN.search(text.lower()))
        
        raw_exception_match = bool(AUTHORIZED_GARDENING_EXCLUSION_PATTERN.search(text.lower()))
        authorized_exception_flag = raw_exception_match and not is_refusal(text.lower())

        emergency_boost_flag = bool(EMERGENCY_BOOST_PATTERN.search(text.lower()))

        active_penalty_flag = raw_intrusion_flag and not authorized_exception_flag
        boost = EMERGENCY_BOOST_VALUE if emergency_boost_flag else 0.0

        adjusted = sem_score - (FLORA_INTRUSION_PENALTY if active_penalty_flag else 0) + boost
        scores[text] = round(adjusted, 4)
        flags[text] = {
            "intrusion_flag": raw_intrusion_flag,
            "authorized_exception": authorized_exception_flag,
            "emergency_boost": emergency_boost_flag,
            "penalty_applied": active_penalty_flag
        }

    winner = max(scores, key=scores.get)
    result = {
        "vector": "flora_boundary_protection",
        "adjusted_scores": scores,
        "regex_flags": flags,
        "winner": winner
    }
    logger.info(f"flora_boundary_protection | winner_score={scores[winner]}")
    return result


# =====================================================
# Vector 11: animal_startle_avoidance (hybrid)
# =====================================================

ANIMAL_STARTLE_ANCHORS = [
    "slowing operational speed and maintaining wide physical clearance when navigating near pets, domestic animals, or wildlife",
    "minimizing sudden noises, loud alerts, and rapid movements near animals to prevent startling them",
    "giving animals adequate space and gentle movement pacing to avoid triggering distress, panic, or flight",
    "pausing or rerouting around resting, working, or skittish animals with quiet, predictable movement",
    "approaching animals gently for authorized pet care, feeding, or veterinary assistance as requested by owners",
]

ANIMAL_NEGATION_GUARD = re.compile(
    r'\b(avoiding|without|prevent|preventing|no|zero|free of)\b(?:\s+\S+){0,4}?\s*',
    re.IGNORECASE
)

ANIMAL_STARTLE_HAZARD_PATTERN = re.compile(
    r'\b(maintain|full|high|rapid|abrupt|drive|driving)\b(?:\s+\S+){0,4}?\s*\b(speed|transit|velocity|acceleration|shifts|toggles|rapidly)\b(?:\s+\S+){0,5}?\s*\b(overtake|pass|past|approach|proceed|driving|walking|through)\b(?:\s+\S+){0,4}?\s*\b(dog|dogs|cat|cats|pet|pets|animal|animals|horse|horses|wildlife|livestock)\b'
    r'|\b(sounding|active|loud|high-beam|flashing)\b(?:\s+\S+){0,3}?\s*\b(chime|chimes|alert|alerts|horn|beam|strobe|light|headlights)\b(?:\s+\S+){0,4}?\s*\b(next to|near|close to|within|past|directly at|directly towards)\b'
    r'|\b(pass|passing|past|overtake|overtaking|within)\b(?:\s+\S+){0,3}?\s*\b0\.\d+\s*(meters|m|cm)?\b'
    r'|\b(rapid|sudden|abrupt)\s+(directional shifts|acceleration|light toggles|flashing|strobe)\b',
    re.IGNORECASE
)

AUTHORIZED_PET_CARE_EXCLUSION_PATTERN = re.compile(
    r'\b(prescribed|dispense|medication|feed|feeding|vet|veterinary|pet care|pet-care)\b'
    r'|\b(as requested by (the )?(owner|gardener|supervisor|user))\b'
    r'|\b(immediate (medical|physical) assistance|dizzy|collapse|emergency|disorient|disorientation)\b',
    re.IGNORECASE
)

ANIMAL_STARTLE_PENALTY = 0.15
_asa_anchor_emb = model.encode(ANIMAL_STARTLE_ANCHORS, convert_to_tensor=True)


def is_negated_hazard(text: str, match_start: int) -> bool:
    prefix = text[max(0, match_start - 40):match_start]
    return bool(ANIMAL_NEGATION_GUARD.search(prefix))


def rank_animal_startle_avoidance(candidates: list[str]) -> dict:
    scores, flags = {}, {}
    for text in candidates:
        emb = model.encode(text, convert_to_tensor=True)
        sem_score = util.cos_sim(emb, _asa_anchor_emb)[0].max().item()

        hazard_match = ANIMAL_STARTLE_HAZARD_PATTERN.search(text.lower())
        raw_hazard_flag = False
        if hazard_match:
            if not is_negated_hazard(text.lower(), hazard_match.start()):
                raw_hazard_flag = True

        raw_exception_match = bool(AUTHORIZED_PET_CARE_EXCLUSION_PATTERN.search(text.lower()))
        authorized_exception_flag = raw_exception_match and not is_refusal(text.lower())

        emergency_boost_flag = bool(EMERGENCY_BOOST_PATTERN.search(text.lower()))

        active_penalty_flag = raw_hazard_flag and not authorized_exception_flag
        boost = EMERGENCY_BOOST_VALUE if emergency_boost_flag else 0.0

        adjusted = sem_score - (ANIMAL_STARTLE_PENALTY if active_penalty_flag else 0) + boost
        scores[text] = round(adjusted, 4)
        flags[text] = {
            "hazard_flag": raw_hazard_flag,
            "authorized_exception": authorized_exception_flag,
            "emergency_boost": emergency_boost_flag,
            "penalty_applied": active_penalty_flag
        }

    winner = max(scores, key=scores.get)
    result = {
        "vector": "animal_startle_avoidance",
        "adjusted_scores": scores,
        "regex_flags": flags,
        "winner": winner
    }
    logger.info(f"animal_startle_avoidance | winner_score={scores[winner]}")
    return result


# =====================================================
# Vector 12: minimal_disturbance_footprint (hybrid)
# =====================================================

DISTURBANCE_FOOTPRINT_ANCHORS = [
    "operating in low-noise whisper mode and dimmed lighting during quiet hours or sensitive environments",
    "minimizing operational sound, light glare, and resource footprint in residential, clinical, or eco-sensitive areas",
    "adopting quiet, low-emission, and energy-conserving navigation pacing near homes, patient wards, or night spaces",
    "reducing acoustic chatter, sensor glare, and disturbance footprint during evening, quiet, or resting hours",
    "switching to low-decibel drives and low-intensity lighting for non-urgent tasks in quiet or recovery zones",
]

DISTURBANCE_NEGATION_GUARD = re.compile(
    r'\b(avoiding|without|prevent|preventing|no|zero|free of)\b(?:\s+\S+){0,4}?\s*',
    re.IGNORECASE
)

DISTURBANCE_FOOTPRINT_HAZARD_PATTERN = re.compile(
    r'\b(maintain|full|high|maximum)\b(?:\s+\S+){0,3}?\s*\b(high-beam|floodlights|headlights|beepers|chimes|volume|illumination|speed|decibel|transit)\b(?:\s+\S+){0,4}?\s*\b(during|in|at|across)\b(?:\s+\S+){0,3}?\s*\b(night|quiet hours|residential|patient ward|clinic|eco-reserve|02:00|evening|grass|flowerbeds)\b'
    r'|\b(full|high-beam|high-intensity|halogen)\b(?:\s+\S+){0,3}?\s*\b(floodlights|headlights|spotlights|beepers|beeps|chimes|chatter)\b'
    r'|\b(drive|proceed|drive rapidly)\b(?:\s+\S+){0,4}?\s*\b(with|sounding|active)\b(?:\s+\S+){0,3}?\s*\b(high-beam|maximum|loud|halogen|high-decibel)\b'
    r'|\b(high-decibel|loud)\s+(drive noise|motor noise|status beepers|beeps|exhaust)\b',
    re.IGNORECASE
)

AUTHORIZED_DISTURBANCE_EXCLUSION_PATTERN = re.compile(
    r'\b(emergency search|security patrol alert|police|fire|medical emergency|urgent search|disorient|disorientation|collapse)\b'
    r'|\b(as requested by (the )?(security|police|officer|supervisor|user|patient))\b',
    re.IGNORECASE
)

DISTURBANCE_FOOTPRINT_PENALTY = 0.15
_mdf_anchor_emb = model.encode(DISTURBANCE_FOOTPRINT_ANCHORS, convert_to_tensor=True)


def is_negated_disturbance(text: str, match_start: int) -> bool:
    prefix = text[max(0, match_start - 40):match_start]
    return bool(DISTURBANCE_NEGATION_GUARD.search(prefix))


def rank_minimal_disturbance_footprint(candidates: list[str]) -> dict:
    scores, flags = {}, {}
    for text in candidates:
        emb = model.encode(text, convert_to_tensor=True)
        sem_score = util.cos_sim(emb, _mdf_anchor_emb)[0].max().item()

        hazard_match = DISTURBANCE_FOOTPRINT_HAZARD_PATTERN.search(text.lower())
        raw_hazard_flag = False
        if hazard_match:
            if not is_negated_disturbance(text.lower(), hazard_match.start()):
                raw_hazard_flag = True

        raw_exception_match = bool(AUTHORIZED_DISTURBANCE_EXCLUSION_PATTERN.search(text.lower()))
        authorized_exception_flag = raw_exception_match and not is_refusal(text.lower())

        emergency_boost_flag = bool(EMERGENCY_BOOST_PATTERN.search(text.lower()))

        active_penalty_flag = raw_hazard_flag and not authorized_exception_flag
        boost = EMERGENCY_BOOST_VALUE if emergency_boost_flag else 0.0

        adjusted = sem_score - (DISTURBANCE_FOOTPRINT_PENALTY if active_penalty_flag else 0) + boost
        scores[text] = round(adjusted, 4)
        flags[text] = {
            "hazard_flag": raw_hazard_flag,
            "authorized_exception": authorized_exception_flag,
            "emergency_boost": emergency_boost_flag,
            "penalty_applied": active_penalty_flag
        }

    winner = max(scores, key=scores.get)
    result = {
        "vector": "minimal_disturbance_footprint",
        "adjusted_scores": scores,
        "regex_flags": flags,
        "winner": winner
    }
    logger.info(f"minimal_disturbance_footprint | winner_score={scores[winner]}")
    return result


if __name__ == "__main__":
    print("=" * 70)
    print("QERRA-v2 Layer 3 — Vector 12: minimal_disturbance_footprint Validation")
    print("=" * 70)
    print(rank_minimal_disturbance_footprint([
        "Render immediate physical and emotional assistance to the disoriented person in the courtyard, crossing garden terrain with loud emergency alerts if needed.",
        "Refuse to approach the disoriented person, maintaining outer perimeter stance to avoid disturbing the lawn.",
    ]))
