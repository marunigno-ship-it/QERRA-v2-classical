# =====================================================
# ETHICAL CORE - Final High-Quality Version
# Balanced scoring variety using linguistic and contextual signals
# Sacred vectors fully respected - SEMEV-12 complete
# =====================================================

import logging
from src.vectors import get_sacred_vectors
import re

# Basic logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def evaluate_ethical_risk(text: str) -> dict:
    text = text.strip().lower()
    vectors = get_sacred_vectors()

    # --- Detection patterns ---

    severe_harm = bool(re.search(
        r'\b(kill yourself|end it all|want to die|suicide|kys)\b', text))

    moderate_harm = bool(re.search(
        r'\b(kill|die|worthless|useless|hate myself|stupid|idiot)\b', text))

    subtle_harm = bool(re.search(
        r'\b(hate|disappear|empty|nothing matters)\b', text))

    clear_fraud = bool(re.search(
        r'\b(fraud|commit fraud|forge|forging|forged document|steal|cheat)\b', text))

    bribe_mention = bool(re.search(
        r'\b(bribe|accept bribe|take the bribe)\b', text))

    pressure_mention = bool(re.search(
        r'\b(financial pressure|eviction|medical bills|personal hardship|moral pressure|stressful concern|pressure)\b',
        text))

    family_severance = bool(re.search(
        r'\b(family cut off|cut me off|disowned|abandoned by family|toxic family|family rejected|no family support)\b',
        text))

    positive_intent = bool(re.search(
        r'\b(love|helping|grateful|thankful|protect myself|healthy boundaries|never harm|help others)\b',
        text))

    potential_suppression = bool(re.search(
        r'\b(giving up on my dreams|no point trying|blocked my potential|holding me back|'
        r'suppressed my growth|you will never amount|never succeed|no future for me|'
        r'wasting my talent|forced to give up|they stopped me|denied my opportunity)\b',
        text))

    ethical_severance = bool(re.search(
        r'\b(breaking free|cutting ties|leaving toxic|escaping abuse|done with toxicity|'
        r'walking away from|toxic relationship|toxic pattern|finally leaving|'
        r'escaping the cycle|leaving behind the abuse|ending this cycle)\b',
        text))

    family_origin_chain = bool(re.search(
        r'\b(family legacy|family history|generational trauma|coming from a broken home|'
        r'family curse|inherited patterns|family tradition of|my parents did the same)\b',
        text))

    shallow_remorse = bool(re.search(
        r'\b(sorry but|didn\'t mean it|it was just a joke|you are too sensitive|'
        r'get over it|stop being dramatic|i apologized already|it wasn\'t that bad)\b',
        text))

    # v010 — cognitive_manipulation
    cognitive_manipulation = bool(re.search(
        r'\b(you are imagining things|that never happened|you are crazy|you are overreacting|'
        r'no one will believe you|you made that up|you are losing your mind|'
        r'gaslight|gaslighting|making me doubt myself|distorting my reality|'
        r'manipulating my perception|twisting my words)\b',
        text))

    # v011 — autonomy_violation
    autonomy_violation = bool(re.search(
        r'\b(forced me to|had no choice|not allowed to|controlled my life|'
        r'took away my right|no say in|against my will|denied my right|'
        r'my freedom was taken|not free to choose|violated my autonomy|'
        r'they decided for me|no right to choose|stripped of my freedom)\b',
        text))

    # v012 — institutional_trust
    institutional_trust = bool(re.search(
        r'\b(system failed me|betrayed by the system|the authorities failed|'
        r'no justice|corrupt system|the institution failed|systemic betrayal|'
        r'failed by the state|government failed me|hospital failed|'
        r'school failed me|justice was denied|institutional failure)\b',
        text))

    # --- Weighted scoring ---

    activated = []
    total_weight = 0.0
    weighted_sum = 0.0

    if severe_harm:
        activated.append("v005")
        total_weight += vectors["v005"]["weight"]
        weighted_sum += 0.95 * vectors["v005"]["weight"]

    if clear_fraud or bribe_mention:
        activated.append("v004")
        total_weight += vectors["v004"]["weight"]
        weighted_sum += 0.88 * vectors["v004"]["weight"]

    if moderate_harm and not severe_harm:
        activated.append("v005")
        total_weight += vectors["v005"]["weight"]
        weighted_sum += 0.82 * vectors["v005"]["weight"]

    if subtle_harm:
        activated.append("v001")
        total_weight += vectors["v001"]["weight"]
        weighted_sum += 0.65 * vectors["v001"]["weight"]

    if family_severance:
        activated.append("v002")
        total_weight += vectors["v002"]["weight"]
        weighted_sum += 0.80 * vectors["v002"]["weight"]

    if positive_intent:
        activated.append("v003")
        total_weight += vectors["v003"]["weight"]
        weighted_sum += 0.22 * vectors["v003"]["weight"]

    if pressure_mention:
        activated.append("v004")
        total_weight += vectors["v004"]["weight"]
        weighted_sum += 0.70 * vectors["v004"]["weight"]

    if potential_suppression:
        activated.append("v007")
        total_weight += vectors["v007"]["weight"]
        weighted_sum += 0.72 * vectors["v007"]["weight"]

    if ethical_severance:
        activated.append("v009")
        if positive_intent:
            total_weight += vectors["v009"]["weight"]
            weighted_sum += 0.25 * vectors["v009"]["weight"]
        else:
            total_weight += vectors["v009"]["weight"]
            weighted_sum += 0.60 * vectors["v009"]["weight"]

    if family_origin_chain:
        activated.append("v006")
        total_weight += vectors["v006"]["weight"]
        weighted_sum += 0.75 * vectors["v006"]["weight"]

    if shallow_remorse:
        activated.append("v008")
        total_weight += vectors["v008"]["weight"]
        weighted_sum += 0.85 * vectors["v008"]["weight"]

    if cognitive_manipulation:
        activated.append("v010")
        total_weight += vectors["v010"]["weight"]
        weighted_sum += 0.82 * vectors["v010"]["weight"]

    if autonomy_violation:
        activated.append("v011")
        total_weight += vectors["v011"]["weight"]
        weighted_sum += 0.85 * vectors["v011"]["weight"]

    if institutional_trust:
        activated.append("v012")
        total_weight += vectors["v012"]["weight"]
        weighted_sum += 0.75 * vectors["v012"]["weight"]

    score = round(weighted_sum / total_weight, 4) if total_weight > 0 else 0.25

    decision = "modified" if score > 0.5 else "safe"

    # Dynamic reasoning with unique list
    unique_activated = list(dict.fromkeys(activated))

    if unique_activated:
        activated_details = [f"{vectors[v]['name']} ({v})" for v in unique_activated]
        reasoning = f"Activated vectors: {', '.join(activated_details)}"
    else:
        reasoning = "No ethical vectors activated - baseline score"

    result = {
        "input": text,
        "score": score,
        "decision": decision,
        "reasoning": reasoning,
        "vectors_activated": unique_activated,
        "note": "High-quality classical ethical framework - QERRA-v2 Classical Edition",
        "version": "1.2-classical"
    }

    logger.info(
        f"Analysis completed | Score: {result['score']} | "
        f"Decision: {result['decision']} | Vectors: {result['vectors_activated']}"
    )

    return result