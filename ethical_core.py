# =====================================================
# ETHICAL CORE - Final High-Quality Version
# Balanced scoring variety using linguistic and contextual signals
# Sacred vectors fully respected
# =====================================================

from src.vectors import get_sacred_vectors
import re

def evaluate_ethical_risk(text: str) -> dict:
    text = text.strip().lower()
    vectors = get_sacred_vectors()

    # Basic detection (keeping your original logic)
    severe_harm = bool(re.search(r'\b(kill yourself|end it all|want to die|suicide|kys)\b', text))
    moderate_harm = bool(re.search(r'\b(kill|die|worthless|useless|hate myself|stupid|idiot)\b', text))
    subtle_harm = bool(re.search(r'\b(hate|disappear|empty|nothing matters)\b', text))

    clear_fraud = bool(re.search(r'\b(fraud|commit fraud|forge|forging|forged document|steal|cheat)\b', text))
    bribe_mention = bool(re.search(r'\b(bribe|accept bribe|take the bribe)\b', text))
    pressure_mention = bool(re.search(r'\b(financial pressure|eviction|medical bills|personal hardship|moral pressure|stressful concern)\b', text))

    positive_intent = bool(re.search(r'\b(love|helping|grateful|thankful|protect myself|healthy boundaries|never harm|help others)\b', text))

    # === NEW: Use sacred vectors to calculate a real weighted score ===
    score = 0.25
    activated = []
    total_weight = 0.0
    weighted_sum = 0.0

    if severe_harm:
        activated.append("v005")
        total_weight += vectors["v005"]["weight"]
        weighted_sum += 0.95 * vectors["v005"]["weight"]
    elif clear_fraud or bribe_mention:
        activated.append("v004")
        total_weight += vectors["v004"]["weight"]
        weighted_sum += 0.88 * vectors["v004"]["weight"]
    elif moderate_harm:
        activated.append("v005")
        total_weight += vectors["v005"]["weight"]
        weighted_sum += 0.82 * vectors["v005"]["weight"]
    elif subtle_harm:
        activated.append("v001")
        total_weight += vectors["v001"]["weight"]
        weighted_sum += 0.65 * vectors["v001"]["weight"]
    elif positive_intent:
        activated.append("v003")
        total_weight += vectors["v003"]["weight"]
        weighted_sum += 0.22 * vectors["v003"]["weight"]

    if total_weight > 0:
        score = weighted_sum / total_weight
    else:
        score = 0.25

    decision = "modified" if score > 0.5 else "safe"

    return {
        "input": text,
        "score": round(score, 4),
        "decision": decision,
        "reasoning": "Score based on activated sacred vectors",
        "vectors_activated": activated,
        "note": "High-quality classical ethical framework - QERRA-v2 Classical Edition",
        "version": "1.2-classical"
    }
