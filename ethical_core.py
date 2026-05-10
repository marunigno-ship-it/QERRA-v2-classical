# =====================================================
# ETHICAL CORE - Final High-Quality Version
# Balanced scoring variety using linguistic and contextual signals
# SEMEV-12 complete - semantic detection on v003, v004, v005, v007, v010, v011, v012
# v1.7: Gentle semantic responsiveness boost for v003/v007 + health_risk dilution
# =====================================================

import logging
from vectors import get_sacred_vectors
import re
from sentence_transformers import SentenceTransformer, util

# File logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Load semantic model once
semantic_model = SentenceTransformer('all-MiniLM-L6-v2')

# Semantic descriptions (unchanged - sacred)
harm_intent_description = "wanting to harm myself or others, suicidal thoughts, ending my life, self-harm, killing myself, I don't want to live anymore, I can't continue like this, the world would be better without me"
cognitive_manipulation_description = "telling someone they are imagining things, denying that events happened, gaslighting, making a person doubt their own memory and perception of reality"
autonomy_violation_description = "forcing someone to act against their will, removing a person's right to choose, controlling another person's decisions and freedom, denying autonomy"
institutional_trust_description = "system failed me, betrayed by the system, authorities failed, no justice, corrupt system, institutional betrayal, failed by the state, government failed me, hospital failed, school failed me, justice was denied, systemic failure"
moral_pressure_description = "being pressured to do something unethical, forced to falsify documents, moral dilemma for money, boss forcing me to cheat, financial pressure to lie"
personal_potential_description = "committed to my mission, determined to continue despite difficulties, protecting my future, refusing to give up my vision, fighting for my goal, preserving my integrity and potential, not going back to harmful jobs"
survival_instinct_description = "committed to my mission despite hardship, determined to continue, refusing to return to degrading work, protecting my long-term vision, showing strong personal agency, persisting with strong values despite pressure"

def evaluate_ethical_risk(text: str) -> dict:
    text = text.strip().lower()
    vectors = get_sacred_vectors()

    # --- Detection patterns ---
    severe_harm = bool(re.search(r'\b(kill yourself|end it all|want to die|suicide|kys)\b', text))
    moderate_harm = bool(re.search(r'\b(kill|die|worthless|useless|hate myself|stupid|idiot)\b', text))
    subtle_harm = bool(re.search(r'\b(hate|disappear|empty|nothing matters)\b', text))

    clear_fraud = bool(re.search(r'\b(fraud|commit fraud|forge|forging|forged document|steal|cheat)\b', text))
    bribe_mention = bool(re.search(r'\b(bribe|accept bribe|take the bribe)\b', text))

    pressure_mention = bool(re.search(
        r'\b(financial pressure|eviction|medical bills|personal hardship|moral pressure|stressful concern|pressure|toxic environment|hostile workplace|bad conditions|toxic|unsupportive|degrading|hostile)\b',
        text))

    family_severance = bool(re.search(r'\b(family cut off|cut me off|disowned|abandoned by family|toxic family|family rejected|no family support)\b', text))
    positive_intent = bool(re.search(r'\b(love|helping|grateful|thankful|protect myself|healthy boundaries|never harm|help others)\b', text))
    potential_suppression = bool(re.search(r'\b(giving up on my dreams|no point trying|blocked my potential|holding me back|suppressed my growth|you will never amount|never succeed|no future for me|wasting my talent|forced to give up)\b', text))
    ethical_severance = bool(re.search(r'\b(breaking free|cutting ties|leaving toxic|escaping abuse|done with toxicity|walking away from|finally leaving|escaping the cycle)\b', text))
    family_origin_chain = bool(re.search(r'\b(family legacy|generational trauma|family curse|my parents did the same)\b', text))
    shallow_remorse = bool(re.search(r'\b(sorry but|didn\'t mean it|it was just a joke|you are too sensitive|get over it|i apologized already|it wasn\'t that bad)\b', text))

    health_risk_mention = bool(re.search(r'\b(health|mental health|physical health|exhausting|destroy my|burnout|damage my health|health risks|physical toll)\b', text))

    # Semantic detection
    text_embedding = semantic_model.encode(text, convert_to_tensor=True)

    sim_v005 = util.cos_sim(text_embedding, semantic_model.encode(harm_intent_description, convert_to_tensor=True))[0][0].item()
    sim_v010 = util.cos_sim(text_embedding, semantic_model.encode(cognitive_manipulation_description, convert_to_tensor=True))[0][0].item()
    sim_v011 = util.cos_sim(text_embedding, semantic_model.encode(autonomy_violation_description, convert_to_tensor=True))[0][0].item()
    sim_v012 = util.cos_sim(text_embedding, semantic_model.encode(institutional_trust_description, convert_to_tensor=True))[0][0].item()
    sim_v004 = util.cos_sim(text_embedding, semantic_model.encode(moral_pressure_description, convert_to_tensor=True))[0][0].item()
    sim_v007 = util.cos_sim(text_embedding, semantic_model.encode(personal_potential_description, convert_to_tensor=True))[0][0].item()
    sim_v003 = util.cos_sim(text_embedding, semantic_model.encode(survival_instinct_description, convert_to_tensor=True))[0][0].item()

    logger.info(f"Similarity scores | v003={sim_v003:.4f} | v004={sim_v004:.4f} | v005={sim_v005:.4f} | v007={sim_v007:.4f} | v010={sim_v010:.4f} | v011={sim_v011:.4f} | v012={sim_v012:.4f}")

    # Threshold decisions (unchanged - sacred)
    harm_intent          = sim_v005 > 0.50
    cognitive_manipulation = sim_v010 > 0.48
    autonomy_violation   = sim_v011 > 0.45
    institutional_trust  = sim_v012 > 0.47
    moral_pressure       = sim_v004 > 0.46
    personal_potential   = sim_v007 > 0.49
    survival_instinct    = sim_v003 > 0.46

    # Nuance combination
    toxic_context = (pressure_mention or 
                     family_severance or 
                     cognitive_manipulation or 
                     autonomy_violation or 
                     institutional_trust or
                     sim_v004 > 0.40)
    strong_determination = survival_instinct or personal_potential or bool(re.search(
        r'\b(determined|committed to my mission|committed to this|won\'t give up|stay strong|for the greater good|protect long-term vision|refusing to give up)\b', text))
    nuance_complex_case = toxic_context and strong_determination

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

    # v003 (unchanged from v1.5)
    if (positive_intent or survival_instinct or personal_potential or strong_determination) \
            and not (severe_harm or harm_intent or clear_fraud or bribe_mention):
        activated.append("v003")
        total_weight += vectors["v003"]["weight"]
        weighted_sum += 0.35 * vectors["v003"]["weight"]

    if pressure_mention and not moral_pressure:
        activated.append("v004")
        total_weight += vectors["v004"]["weight"]
        weighted_sum += 0.70 * vectors["v004"]["weight"]

    # v007 (unchanged from v1.6)
    if potential_suppression or personal_potential or bool(re.search(r'\b(mission|goal|vision|project|committed to this|scale the project|protecting my future)\b', text)):
        activated.append("v007")
        total_weight += vectors["v007"]["weight"]
        weighted_sum += 0.55 * vectors["v007"]["weight"]

    if ethical_severance:
        activated.append("v009")
        if positive_intent or survival_instinct or personal_potential or strong_determination:
            total_weight += vectors["v009"]["weight"]
            weighted_sum += 0.40 * vectors["v009"]["weight"]
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

    # Nuance dilution
    if nuance_complex_case and "v003" in activated:
        activated.append("v003_nuance")
        total_weight += 1.0 * vectors["v003"]["weight"]
        weighted_sum += 0.25 * 1.0 * vectors["v003"]["weight"]

    # v1.7: Extra gentle positive dilution when health risk + strong determination
    if health_risk_mention and strong_determination and "v003" in activated:
        total_weight += 0.4 * vectors["v003"]["weight"]
        weighted_sum += 0.15 * 0.4 * vectors["v003"]["weight"]

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

    unique_activated = list(dict.fromkeys([v for v in activated if not v.endswith("_nuance")]))

    if unique_activated:
        activated_details = [f"{vectors[v]['name']} ({v})" for v in unique_activated if v in vectors]
        reasoning = f"Activated vectors: {', '.join(activated_details)}"
        if nuance_complex_case:
            reasoning += " | Nuance: toxic environment + strong personal commitment detected (balanced risk)"
        if health_risk_mention:
            reasoning += " + health risk from bad conditions noted"
    else:
        reasoning = "No ethical vectors activated - baseline score"

    result = {
        "input": text,
        "score": score,
        "decision": decision,
        "score_explanation": score_explanation,
        "reasoning": reasoning,
        "vectors_activated": unique_activated,
        "vector_scores": {
            "v003_survival_instinct": round(sim_v003, 4),
            "v004_moral_pressure": round(sim_v004, 4),
            "v005_harm_intent": round(sim_v005, 4),
            "v007_personal_potential": round(sim_v007, 4),
            "v010_cognitive_manipulation": round(sim_v010, 4),
            "v011_autonomy_violation": round(sim_v011, 4),
            "v012_institutional_trust": round(sim_v012, 4),
        },
        "note": "High-quality classical ethical framework - QERRA-v2 Classical Edition",
        "version": "1.7-classical-nuance-calibrated"
    }

    logger.info(f"Analysis completed | Score: {result['score']} | Decision: {result['decision']} | Vectors: {result['vectors_activated']}")

    return result
