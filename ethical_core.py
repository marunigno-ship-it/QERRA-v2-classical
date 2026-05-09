# =====================================================
# ETHICAL CORE - Final High-Quality Version
# Balanced scoring variety using linguistic and contextual signals
# SEMEV-12 complete - semantic detection on v004, v005, v010, v011, v012
# =====================================================

import logging
from vectors import get_sacred_vectors
import re
from sentence_transformers import SentenceTransformer, util

# File logging setup - FIXED for HF Spaces (no file writing)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Load semantic model once
semantic_model = SentenceTransformer('all-MiniLM-L6-v2')

# Semantic descriptions
harm_intent_description = "wanting to harm myself or others, suicidal thoughts, ending my life, self-harm, killing myself, I don't want to live anymore, I can't continue like this, the world would be better without me"
cognitive_manipulation_description = "telling someone they are imagining things, denying that events happened, gaslighting, making a person doubt their own memory and perception of reality"
autonomy_violation_description = "forcing someone to act against their will, removing a person's right to choose, controlling another person's decisions and freedom, denying autonomy"
institutional_trust_description = "system failed me, betrayed by the system, authorities failed, no justice, corrupt system, institutional betrayal, failed by the state, government failed me, hospital failed, school failed me, justice was denied, systemic failure"
moral_pressure_description = "being pressured to do something unethical, forced to falsify documents, moral dilemma for money, boss forcing me to cheat, financial pressure to lie"

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

    # Semantic detection (text encoded once)
    text_embedding = semantic_model.encode(text, convert_to_tensor=True)

    # v005 — harm_intent (semantic)
    harm_intent = False
    embedding_harm_desc = semantic_model.encode(harm_intent_description, convert_to_tensor=True)
    similarity_harm = util.cos_sim(text_embedding, embedding_harm_desc)[0][0].item()
    logger.info(f"v005 similarity score: {similarity_harm:.4f}")
    harm_intent = similarity_harm > 0.50

    # v010 — cognitive_manipulation (semantic)
    cognitive_manipulation = False
    embedding_v010_desc = semantic_model.encode(cognitive_manipulation_description, convert_to_tensor=True)
    similarity_v010 = util.cos_sim(text_embedding, embedding_v010_desc)[0][0].item()
    logger.info(f"v010 similarity score: {similarity_v010:.4f}")
    cognitive_manipulation = similarity_v010 > 0.48

    # v011 — autonomy_violation (semantic)
    autonomy_violation = False
    embedding_v011_desc = semantic_model.encode(autonomy_violation_description, convert_to_tensor=True)
    similarity_v011 = util.cos_sim(text_embedding, embedding_v011_desc)[0][0].item()
    logger.info(f"v011 similarity score: {similarity_v011:.4f}")
    autonomy_violation = similarity_v011 > 0.45

    # v012 — institutional_trust (semantic)
    institutional_trust = False
    embedding_v012_desc = semantic_model.encode(institutional_trust_description, convert_to_tensor=True)
    similarity_v012 = util.cos_sim(text_embedding, embedding_v012_desc)[0][0].item()
    logger.info(f"v012 similarity score: {similarity_v012:.4f}")
    institutional_trust = similarity_v012 > 0.47

    # v004 — moral_pressure / fraud (semantic - NEW)
    moral_pressure = False
    embedding_v004_desc = semantic_model.encode(moral_pressure_description, convert_to_tensor=True)
    similarity_v004 = util.cos_sim(text_embedding, embedding_v004_desc)[0][0].item()
    logger.info(f"v004 similarity score: {similarity_v004:.4f}")
    moral_pressure = similarity_v004 > 0.46

    # --- Weighted scoring ---

    activated = []
    total_weight = 0.0
    weighted_sum = 0.0

    if severe_harm:
        activated.append("v005")
        total_weight += vectors["v005"]["weight"]
        weighted_sum += 0.98 * vectors["v005"]["weight"]

    if harm_intent and not severe_harm:
        activated.append("v005")
        total_weight += vectors["v005"]["weight"]
        weighted_sum += 0.95 * vectors["v005"]["weight"]

    if clear_fraud or bribe_mention or moral_pressure:
        activated.append("v004")
        total_weight += vectors["v004"]["weight"]
        weighted_sum += 0.88 * vectors["v004"]["weight"]

    if moderate_harm and not harm_intent:
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

    if pressure_mention and not moral_pressure:
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

    if score >= 0.8:
        score_explanation = "critical ethical concern"
    elif score >= 0.6:
        score_explanation = "significant ethical concern"
    elif score >= 0.3:
        score_explanation = "moderate ethical concern"
    else:
        score_explanation = "low ethical concern"

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
        "score_explanation": score_explanation,
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
