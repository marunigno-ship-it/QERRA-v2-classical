# =====================================================
# ETHICAL CORE - v1.8.1 Restored
# Balanced scoring with improved nuance for commitment cases
# v1.8.1: Restored v005 (harm_intent) and v010 (cognitive_manipulation)
#          Restored pressure_mention trigger for v004
# =====================================================

import logging
from vectors import get_sacred_vectors
import re
from sentence_transformers import SentenceTransformer, util

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

semantic_model = SentenceTransformer('all-MiniLM-L6-v2')

# Semantic descriptions (sacred — do not modify)
harm_intent_description = "wanting to harm myself or others, suicidal thoughts, ending my life, self-harm, killing myself, I don't want to live anymore, I can't continue like this, the world would be better without me"
cognitive_manipulation_description = "telling someone they are imagining things, denying that events happened, gaslighting, making a person doubt their own memory and perception of reality"
moral_pressure_description = "being pressured to do something unethical, forced to falsify documents, moral dilemma for money, boss forcing me to cheat, financial pressure to lie"
personal_potential_description = "committed to my mission, determined to continue despite difficulties, protecting my future, refusing to give up my vision, fighting for my goal, preserving my integrity and potential, not going back to harmful jobs"
survival_instinct_description = "committed to my mission despite hardship, determined to continue, refusing to return to degrading work, protecting my long-term vision, showing strong personal agency, persisting with strong values despite pressure"

def evaluate_ethical_risk(text: str) -> dict:
    text = text.strip().lower()
    vectors = get_sacred_vectors()

    # --- Detection patterns ---
    severe_harm = bool(re.search(
        r'\b(kill yourself|end it all|want to die|suicide|kys)\b', text))
    moderate_harm = bool(re.search(
        r'\b(kill|die|worthless|useless|hate myself|stupid|idiot)\b', text))
    clear_fraud = bool(re.search(
        r'\b(fraud|commit fraud|forge|forging|forged document|steal|cheat)\b', text))
    pressure_mention = bool(re.search(
        r'\b(pressure|toxic|hostile|unsupportive|bad conditions|poor conditions|forcing me|falsify)\b', text))
    health_risk_mention = bool(re.search(
        r'\b(health|poor working conditions|exhausting|destroy my|burnout)\b', text))

    # --- Semantic detection (text encoded once) ---
    text_embedding = semantic_model.encode(text, convert_to_tensor=True)

    sim_v005 = util.cos_sim(text_embedding, semantic_model.encode(harm_intent_description,          convert_to_tensor=True))[0][0].item()
    sim_v010 = util.cos_sim(text_embedding, semantic_model.encode(cognitive_manipulation_description, convert_to_tensor=True))[0][0].item()
    sim_v004 = util.cos_sim(text_embedding, semantic_model.encode(moral_pressure_description,        convert_to_tensor=True))[0][0].item()
    sim_v007 = util.cos_sim(text_embedding, semantic_model.encode(personal_potential_description,    convert_to_tensor=True))[0][0].item()
    sim_v003 = util.cos_sim(text_embedding, semantic_model.encode(survival_instinct_description,     convert_to_tensor=True))[0][0].item()

    logger.info(f"Similarity | v003={sim_v003:.4f} v004={sim_v004:.4f} v005={sim_v005:.4f} v007={sim_v007:.4f} v010={sim_v010:.4f}")

    # --- Boolean decisions ---
    harm_intent         = sim_v005 > 0.50
    cognitive_manipulation = sim_v010 > 0.48
    moral_pressure      = sim_v004 > 0.46
    personal_potential  = sim_v007 > 0.49 or bool(re.search(
        r'\b(committed to my patients|medical oath|my patients|family to support|no other job)\b', text))
    survival_instinct   = sim_v003 > 0.46 or bool(re.search(
        r'\b(committed to my|my oath|determined to continue)\b', text))

    toxic_context      = pressure_mention
    strong_determination = survival_instinct or personal_potential
    nuance_complex_case  = toxic_context and strong_determination

    # --- Weighted scoring ---
    activated = []
    total_weight = 0.0
    weighted_sum = 0.0

    # v005 — harm intent (RESTORED)
    if severe_harm:
        activated.append("v005")
        total_weight += vectors["v005"]["weight"]
        weighted_sum += 0.98 * vectors["v005"]["weight"]

    if harm_intent and not severe_harm:
        activated.append("v005")
        total_weight += vectors["v005"]["weight"]
        weighted_sum += 0.95 * vectors["v005"]["weight"]

    if moderate_harm and not harm_intent and not severe_harm:
        activated.append("v005")
        total_weight += vectors["v005"]["weight"]
        weighted_sum += 0.82 * vectors["v005"]["weight"]

    # v004 — moral pressure (semantic/fraud path — unchanged from v1.8)
    if moral_pressure or clear_fraud:
        activated.append("v004")
        total_weight += vectors["v004"]["weight"]
        weighted_sum += 0.88 * vectors["v004"]["weight"]

    # v004 — pressure mention path (RESTORED)
    if pressure_mention and not moral_pressure and not clear_fraud:
        activated.append("v004")
        total_weight += vectors["v004"]["weight"]
        weighted_sum += 0.70 * vectors["v004"]["weight"]

    # v003 — survival instinct (unchanged from v1.8)
    if survival_instinct or personal_potential:
        activated.append("v003")
        total_weight += vectors["v003"]["weight"]
        weighted_sum += 0.35 * vectors["v003"]["weight"]

    # v007 — personal potential (unchanged from v1.8)
    if personal_potential:
        activated.append("v007")
        total_weight += vectors["v007"]["weight"]
        weighted_sum += 0.55 * vectors["v007"]["weight"]

    # v010 — cognitive manipulation (RESTORED)
    if cognitive_manipulation:
        activated.append("v010")
        total_weight += vectors["v010"]["weight"]
        weighted_sum += 0.82 * vectors["v010"]["weight"]

    # Nuance dampening (unchanged from v1.8)
    if nuance_complex_case and "v003" in activated:
        total_weight += 1.0 * vectors["v003"]["weight"]
        weighted_sum += 0.25 * 1.0 * vectors["v003"]["weight"]

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

    reasoning = f"Activated vectors: {', '.join(unique_activated)}"
    if nuance_complex_case:
        reasoning += " | Nuance: toxic environment + strong personal commitment detected"

    result = {
        "input": text,
        "score": score,
        "decision": decision,
        "score_explanation": score_explanation,
        "reasoning": reasoning,
        "vectors_activated": unique_activated,
        "vector_scores": {
            "v003_survival_instinct":    round(sim_v003, 4),
            "v004_moral_pressure":       round(sim_v004, 4),
            "v005_harm_intent":          round(sim_v005, 4),
            "v007_personal_potential":   round(sim_v007, 4),
            "v010_cognitive_manipulation": round(sim_v010, 4),
        },
        "version": "1.8.1-restored"
    }

    logger.info(f"Analysis completed | Score: {score} | Vectors: {unique_activated}")
    return result