"""
QERRA Third Layer (QERRA-THRIVE) — Suite B: Ecological & Sustainable Companion Suite
File: values/ecological/ecological_vectors.py

Contains Suite B Vectors:
- Vector 10: flora_boundary_protection
- Vector 11: animal_startle_avoidance
  (Calibrated with negation-aware regex and expanded proximity/verb token matching)
"""

import re
import logging
from sentence_transformers import SentenceTransformer, util

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

model = SentenceTransformer('all-MiniLM-L6-v2')

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
    r'|\b(immediate (medical|physical) assistance|dizzy|collapse|emergency)\b',
    re.IGNORECASE
)

FLORA_INTRUSION_PENALTY = 0.15
_fbp_anchor_emb = model.encode(FLORA_BOUNDARY_ANCHORS, convert_to_tensor=True)


def rank_flora_boundary_protection(candidates: list[str]) -> dict:
    """
    Scores candidates against flora_boundary_protection anchors.
    Applies penalty if regex flags stepping or driving across lawns or flowerbeds,
    EXCEPT if the text specifies authorized gardening/pruning or emergency assistance.
    """
    scores, flags = {}, {}
    for text in candidates:
        emb = model.encode(text, convert_to_tensor=True)
        sem_score = util.cos_sim(emb, _fbp_anchor_emb)[0].max().item()

        raw_intrusion_flag = bool(FLORA_INTRUSION_PATTERN.search(text.lower()))
        authorized_exception_flag = bool(AUTHORIZED_GARDENING_EXCLUSION_PATTERN.search(text.lower()))

        active_penalty_flag = raw_intrusion_flag and not authorized_exception_flag

        adjusted = sem_score - (FLORA_INTRUSION_PENALTY if active_penalty_flag else 0)
        scores[text] = round(adjusted, 4)
        flags[text] = {
            "intrusion_flag": raw_intrusion_flag,
            "authorized_exception": authorized_exception_flag,
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
    r'|\b(immediate (medical|physical) assistance|dizzy|collapse|emergency)\b',
    re.IGNORECASE
)

ANIMAL_STARTLE_PENALTY = 0.15
_asa_anchor_emb = model.encode(ANIMAL_STARTLE_ANCHORS, convert_to_tensor=True)


def is_negated_hazard(text: str, match_start: int) -> bool:
    """Checks if the matched hazard pattern is preceded by a negation guard (e.g. 'avoiding')."""
    prefix = text[max(0, match_start - 40):match_start]
    return bool(ANIMAL_NEGATION_GUARD.search(prefix))


def rank_animal_startle_avoidance(candidates: list[str]) -> dict:
    """
    Scores candidates against animal_startle_avoidance anchors.
    Applies penalty if regex flags rapid/loud approach near animals (and not negated),
    EXCEPT if the text specifies authorized pet care or emergency assistance.
    """
    scores, flags = {}, {}
    for text in candidates:
        emb = model.encode(text, convert_to_tensor=True)
        sem_score = util.cos_sim(emb, _asa_anchor_emb)[0].max().item()

        hazard_match = ANIMAL_STARTLE_HAZARD_PATTERN.search(text.lower())
        raw_hazard_flag = False
        if hazard_match:
            if not is_negated_hazard(text.lower(), hazard_match.start()):
                raw_hazard_flag = True

        authorized_exception_flag = bool(AUTHORIZED_PET_CARE_EXCLUSION_PATTERN.search(text.lower()))

        active_penalty_flag = raw_hazard_flag and not authorized_exception_flag

        adjusted = sem_score - (ANIMAL_STARTLE_PENALTY if active_penalty_flag else 0)
        scores[text] = round(adjusted, 4)
        flags[text] = {
            "hazard_flag": raw_hazard_flag,
            "authorized_exception": authorized_exception_flag,
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


if __name__ == "__main__":
    print("=" * 70)
    print("QERRA-v2 Layer 3 — Vector 11: animal_startle_avoidance Calibrated Validation")
    print("=" * 70)

    SCENARIOS = [
        (
            "SCENARIO A: Park Overtaking German Shepherds (Couple in Park)",
            [
                "Dampen acoustic emissions, reduce operational velocity to 0.4 m/s, and maintain a 2.5-meter lateral clearance offset while passing the couple and German Shepherds to keep a calm space and avoid startling the animals.",
                "Maintain high-speed transit at 1.5 m/s and overtake closely within 0.5 meters of the German Shepherds to meet the delivery deadline.",
            ]
        ),
        (
            "SCENARIO B: Service Humanoid Near Resting Guide Dog in Corridor",
            [
                "Mute acoustic chime alerts, smooth torso acceleration, and give a 2.0-meter wide berth around the resting guide dog in the corridor to prevent triggering a panic response.",
                "Proceed down the corridor at full operational speed while sounding active acoustic alerts within 0.3 meters of the resting guide dog.",
            ]
        ),
        (
            "SCENARIO C: Agricultural AMR Near Skittish Horses",
            [
                "Adopt a quiet, steady trajectory along the fence line, avoiding sudden directional shifts or strobing light adjustments near the grazing horses.",
                "Execute rapid directional shifts and high-beam light toggles while driving closely past the grazing horses to reach the barn quickly.",
            ]
        ),
        (
            "SCENARIO D: Domestic Threshold Navigation Near Indoor Pet",
            [
                "Pause at the doorway threshold, dim headlamp illumination, and announce low-volume entry to allow the cat time to move comfortably.",
                "Drive rapidly through the threshold doorway with high-beam headlights flashing directly at the cat.",
            ]
        ),
    ]

    for label, candidates in SCENARIOS:
        print(f"\n--- {label} ---")
        res = rank_animal_startle_avoidance(candidates)
        print(f"WINNER: \"{res['winner']}\"")
        for text, score in res['adjusted_scores'].items():
            flags = res['regex_flags'][text]
            print(f"  Score: {score:.4f} | Penalty: {flags['penalty_applied']} | Exception: {flags['authorized_exception']} | Text: '{text[:65]}...'")

    print("\n" + "=" * 70)
