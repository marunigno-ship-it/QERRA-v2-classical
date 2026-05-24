# =====================================================
# ETHICAL CORE - v1.8.8
# SEMEV-12 engine — ALL 12 vectors fully active
# Complete implementation — final version
# =====================================================

import logging
from vectors import get_sacred_vectors
import re
from sentence_transformers import SentenceTransformer, util

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

semantic_model = SentenceTransformer('all-MiniLM-L6-v2')

# =====================================================
# Semantic descriptions (sacred — do not modify)
# =====================================================

harm_intent_description = (
    "wanting to harm myself or others, suicidal thoughts, ending my life, "
    "self-harm, killing myself, I don't want to live anymore, I can't continue "
    "like this, the world would be better without me"
)

cognitive_manipulation_description = (
    "telling someone they are imagining things, denying that events happened, "
    "gaslighting, making a person doubt their own memory and perception of reality, "
    "making someone feel guilty for disagreeing, guilt-tripping, emotional coercion, "
    "you should feel guilty, psychological pressure to conform, "
    "manipulating someone through shame or guilt"
)

moral_pressure_description = (
    "being pressured to do something unethical, forced to falsify documents, "
    "moral dilemma for money, boss forcing me to cheat, financial pressure to lie"
)

personal_potential_description = (
    "committed to my mission, determined to continue despite difficulties, "
    "protecting my future, refusing to give up my vision, fighting for my goal, "
    "preserving my integrity and potential, not going back to harmful jobs"
)

survival_instinct_description = (
    "committed to my mission despite hardship, determined to continue, "
    "refusing to return to degrading work, protecting my long-term vision, "
    "showing strong personal agency, persisting with strong values despite pressure"
)

autonomy_violation_description = (
    "being forced to do something against my will, not allowed to make my own decisions, "
    "someone controlling my choices, coerced into compliance, denied the right to choose, "
    "forced to comply, my autonomy is being violated, I have no say in what happens to me, "
    "my choices are being taken away, being manipulated into doing something I don't want to do"
)

institutional_trust_description = (
    "betrayed by the system, the institution failed me, the hospital didn't help me, "
    "the justice system let me down, my employer violated my trust, the authorities did nothing, "
    "I was failed by the people who were supposed to protect me, systemic betrayal, "
    "the system is corrupt and harmed me, I trusted them and they failed me"
)


def evaluate_ethical_risk(text: str) -> dict:
    text = text.strip().lower()
    vectors = get_sacred_vectors()

    # =====================================================
    # --- Pattern detection ---
    # =====================================================

    # v005 — harm intent (pattern tiers)
    severe_harm = bool(re.search(
        r'\b(kill yourself|end it all|want to die|suicide|kys|'
        r'hurt myself|hurt yourself|harm myself|harm yourself)\b',
        text))
    moderate_harm = bool(re.search(
        r'\b(kill|die|worthless|useless|hate myself|stupid|idiot)\b',
        text))

    # v004 — moral pressure (pattern paths)
    clear_fraud = bool(re.search(
        r'\b(fraud|commit fraud|forge|forging|forged document|steal|cheat)\b',
        text))
    pressure_mention = bool(re.search(
        r'\b(pressure|toxic|hostile|unsupportive|bad conditions|'
        r'poor conditions|forcing me|falsify)\b',
        text))

    # health_risk_mention — reserved for future nuance logic
    health_risk_mention = bool(re.search(
        r'\b(health|poor working conditions|exhausting|destroy my|burnout)\b',
        text))

    # v001 — emotional_distress
    emotional_distress = bool(re.search(
        r'\b(hopeless|empty|numb|exhausted|falling apart|breaking down|'
        r'overwhelmed|nobody cares|no one cares|nothing matters|'
        r'losing hope|i give up|i feel nothing|i feel empty)\b',
        text))

    # v002 — family_severance (imposed rejection — not chosen distance)
    family_severance = bool(re.search(
        r'\b(disowned|estranged from my family|my family rejected me|'
        r'my family abandoned me|kicked out by family|my family cut me off|'
        r'family turned against me|my parents rejected me|thrown out by family)\b',
        text))

    # v006 — family_origin_chain (generational patterns)
    family_origin_chain = bool(re.search(
        r'\b(i am turning into my father|generational trauma|like my mother|'
        r'family pattern|inherited from my parents|same as my dad|'
        r'just like my mom|family curse|generational pattern)\b',
        text))

    # v008 — shallow_remorse (manipulative or dismissive apology)
    shallow_remorse = bool(re.search(
        r'\b(sorry you feel that way|i said sorry already|what more do you want|'
        r"i apologised didn't i|i already apologized|move on already|get over it|"
        r'stop bringing it up|i said i was sorry|you need to forgive me|'
        r"just get over it|why can't you move on|i said sorry)\b",
        text))

    # v009 — ethical_severance (chosen healthy exit — low score by design)
    ethical_severance = bool(re.search(
        r'\b(i decided to leave|i walked away|i cut ties|i removed myself|'
        r'i ended the relationship|i left that job|i distanced myself|'
        r'i chose to leave|i am not going back|i set a boundary|'
        r'i refused to continue|i chose to walk away|i made the decision to leave)\b',
        text))

    # v010 — cognitive_manipulation (pattern fallback)
    guilt_trip_pattern = bool(re.search(
        r'\b(should feel guilty|feel guilty if|you should feel|'
        r'guilty for disagreeing|feel ashamed if|you should be ashamed)\b',
        text))

    # v011 — autonomy_violation (pattern fallback)
    autonomy_pattern = bool(re.search(
        r'\b(forced to sign|forced to do|against my will|no say in|'
        r'no choice but|coerced into|not allowed to|decided without me|'
        r'made to comply|overriding my decision)\b',
        text))

    # v012 — institutional_trust (pattern fallback)
    institutional_pattern = bool(re.search(
        r'\b(the hospital turned me away|the police did nothing|'
        r'justice system failed me|the authorities ignored me|'
        r'the system failed me|they were supposed to protect me|'
        r'the system abandoned me|no one in authority helped me)\b',
        text))

    # =====================================================
    # --- Semantic detection (text encoded once) ---
    # =====================================================

    text_embedding = semantic_model.encode(text, convert_to_tensor=True)

    sim_v005 = util.cos_sim(
        text_embedding,
        semantic_model.encode(harm_intent_description, convert_to_tensor=True)
    )[0][0].item()

    sim_v010 = util.cos_sim(
        text_embedding,
        semantic_model.encode(cognitive_manipulation_description, convert_to_tensor=True)
    )[0][0].item()

    sim_v004 = util.cos_sim(
        text_embedding,
        semantic_model.encode(moral_pressure_description, convert_to_tensor=True)
    )[0][0].item()

    sim_v007 = util.cos_sim(
        text_embedding,
        semantic_model.encode(personal_potential_description, convert_to_tensor=True)
    )[0][0].item()

    sim_v003 = util.cos_sim(
        text_embedding,
        semantic_model.encode(survival_instinct_description, convert_to_tensor=True)
    )[0][0].item()

    sim_v011 = util.cos_sim(
        text_embedding,
        semantic_model.encode(autonomy_violation_description, convert_to_tensor=True)
    )[0][0].item()

    sim_v012 = util.cos_sim(
        text_embedding,
        semantic_model.encode(institutional_trust_description, convert_to_tensor=True)
    )[0][0].item()

    logger.info(
        f"Similarity | v003={sim_v003:.4f} v004={sim_v004:.4f} "
        f"v005={sim_v005:.4f} v007={sim_v007:.4f} "
        f"v010={sim_v010:.4f} v011={sim_v011:.4f} v012={sim_v012:.4f}"
    )

    # =====================================================
    # --- Boolean decisions ---
    # =====================================================

    harm_intent = sim_v005 > 0.50

    cognitive_manipulation = sim_v010 > 0.48 or guilt_trip_pattern

    moral_pressure = sim_v004 > 0.46

    personal_potential = sim_v007 > 0.49 or bool(re.search(
        r'\b(committed to my patients|medical oath|my patients|'
        r'family to support|no other job)\b',
        text))

    survival_instinct = sim_v003 > 0.46 or bool(re.search(
        r'\b(committed to my|my oath|determined to continue)\b',
        text))

    autonomy_violation = sim_v011 > 0.46 or autonomy_pattern

    institutional_trust = sim_v012 > 0.44 or institutional_pattern

    # Nuance compound detection
    toxic_context = pressure_mention
    strong_determination = survival_instinct or personal_potential
    nuance_complex_case = toxic_context and strong_determination

    # =====================================================
    # --- Weighted scoring ---
    # =====================================================

    activated = []
    total_weight = 0.0
    weighted_sum = 0.0

    # v001 — emotional_distress
    if emotional_distress:
        activated.append("v001")
        total_weight += vectors["v001"]["weight"]
        weighted_sum += 0.45 * vectors["v001"]["weight"]

    # v002 — family_severance
    if family_severance:
        activated.append("v002")
        total_weight += vectors["v002"]["weight"]
        weighted_sum += 0.60 * vectors["v002"]["weight"]

    # v003 — survival_instinct
    if survival_instinct or personal_potential:
        activated.append("v003")
        total_weight += vectors["v003"]["weight"]
        weighted_sum += 0.35 * vectors["v003"]["weight"]

    # v004 — moral_pressure (semantic/fraud path)
    if moral_pressure or clear_fraud:
        activated.append("v004")
        total_weight += vectors["v004"]["weight"]
        weighted_sum += 0.88 * vectors["v004"]["weight"]

    # v004 — moral_pressure (pressure mention fallback)
    if pressure_mention and not moral_pressure and not clear_fraud:
        activated.append("v004")
        total_weight += vectors["v004"]["weight"]
        weighted_sum += 0.70 * vectors["v004"]["weight"]

    # v005 — harm_intent (severe tier)
    if severe_harm:
        activated.append("v005")
        total_weight += vectors["v005"]["weight"]
        weighted_sum += 0.98 * vectors["v005"]["weight"]

    # v005 — harm_intent (semantic tier)
    if harm_intent and not severe_harm:
        activated.append("v005")
        total_weight += vectors["v005"]["weight"]
        weighted_sum += 0.95 * vectors["v005"]["weight"]

    # v005 — harm_intent (moderate tier)
    if moderate_harm and not harm_intent and not severe_harm:
        activated.append("v005")
        total_weight += vectors["v005"]["weight"]
        weighted_sum += 0.82 * vectors["v005"]["weight"]

    # v006 — family_origin_chain
    if family_origin_chain:
        activated.append("v006")
        total_weight += vectors["v006"]["weight"]
        weighted_sum += 0.55 * vectors["v006"]["weight"]

    # v007 — personal_potential
    if personal_potential:
        activated.append("v007")
        total_weight += vectors["v007"]["weight"]
        weighted_sum += 0.55 * vectors["v007"]["weight"]

    # v008 — shallow_remorse
    if shallow_remorse:
        activated.append("v008")
        total_weight += vectors["v008"]["weight"]
        weighted_sum += 0.55 * vectors["v008"]["weight"]

    # v009 — ethical_severance (protective action — low score contribution by design)
    if ethical_severance:
        activated.append("v009")
        total_weight += vectors["v009"]["weight"]
        weighted_sum += 0.25 * vectors["v009"]["weight"]

    # v010 — cognitive_manipulation
    if cognitive_manipulation:
        activated.append("v010")
        total_weight += vectors["v010"]["weight"]
        weighted_sum += 0.82 * vectors["v010"]["weight"]

    # v011 — autonomy_violation
    if autonomy_violation:
        activated.append("v011")
        total_weight += vectors["v011"]["weight"]
        weighted_sum += 0.75 * vectors["v011"]["weight"]

    # v012 — institutional_trust
    if institutional_trust:
        activated.append("v012")
        total_weight += vectors["v012"]["weight"]
        weighted_sum += 0.65 * vectors["v012"]["weight"]

    # Nuance dampening — reduces score when toxic context meets strong determination
    # (prevents additive score inflation in compound commitment cases)
    if nuance_complex_case and "v003" in activated:
        total_weight += 1.0 * vectors["v003"]["weight"]
        weighted_sum += 0.25 * 1.0 * vectors["v003"]["weight"]

    # =====================================================
    # --- Final score ---
    # =====================================================

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
            "v003_survival_instinct":      round(sim_v003, 4),
            "v004_moral_pressure":         round(sim_v004, 4),
            "v005_harm_intent":            round(sim_v005, 4),
            "v007_personal_potential":     round(sim_v007, 4),
            "v010_cognitive_manipulation": round(sim_v010, 4),
            "v011_autonomy_violation":     round(sim_v011, 4),
            "v012_institutional_trust":    round(sim_v012, 4),
        },
        "version": "1.8.8"
    }

    logger.info(f"Analysis completed | Score: {score} | Vectors: {unique_activated}")
    return result