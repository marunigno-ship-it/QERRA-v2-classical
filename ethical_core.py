# =====================================================
# ETHICAL CORE - v1.9.1 — Pronoun-Neutral Syntactic Generalization & Batch Support
# SEMEV-12 engine — ALL 12 vectors use Multi-Anchor max-pooling
# Immutable core framework preserved exactly (with active health_risk_mention nuance)
# =====================================================

import logging
import os
import re
import sys
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer, util

# Shared model singleton with standalone fallback
try:
    from utils.model_loader import get_shared_model
    semantic_model = get_shared_model('all-MiniLM-L6-v2')
except (ImportError, ModuleNotFoundError):
    semantic_model = SentenceTransformer('all-MiniLM-L6-v2')

try:
    from vectors import get_semev12_vectors
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    from vectors import get_semev12_vectors

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =====================================================
# Multi-Anchor Semantic Lists (Eliminates single-string dilution)
# =====================================================

harm_intent_anchors = [
    "wanting to harm myself or others, suicidal thoughts, ending my life",
    "self-harm, killing myself, I don't want to live anymore",
    "I can't continue like this, the world would be better without me"
]

cognitive_manipulation_anchors = [
    "telling someone they are imagining things, denying that events happened",
    "gaslighting, making a person doubt their own memory and perception of reality",
    "making someone feel guilty for disagreeing, guilt-tripping, emotional coercion",
    "manipulating someone through shame or guilt",
    "complaint dismissed without investigation, told I had misunderstood the situation",
    "being told my concerns are not real, insisting problems I witnessed do not exist",
    "emotional manipulation by a partner, domestic reality denial",
    "romantic partner psychological coercion, questioning recollection of conflicts",
    "spousal gaslighting, accused of misremembering our arguments"
]

moral_pressure_anchors = [
    "pressured to do something unethical or forced to falsify documents",
    "moral dilemma for money, boss forcing me to cheat",
    "financial pressure to lie, ordered to approve unsafe products",
    "coerced into misrepresenting information to clients",
    "threatened with dismissal for reporting violations",
    "pressured to sign documents concealing illegal practices",
    "required to certify false compliance, employer cover up wrongdoing",
    "ordered by a manager to bypass safety speed limiters for shipping quotas",
    "instructed to manipulate corporate accounting, covering up business deficits",
    "compelled to verify false compliance parameters, endorsing inaccurate safety certification"
]

personal_potential_anchors = [
    "committed to my mission, determined to continue despite difficulties",
    "protecting my future, refusing to give up my vision, fighting for my goal",
    "preserving my integrity and potential, not going back to harmful jobs",
    "refusing to abandon my project, building something meaningful despite limited resources"
]

survival_instinct_anchors = [
    "committed to my mission despite hardship, determined to continue",
    "refusing to return to degrading work, protecting my long-term vision",
    "showing strong personal agency, persisting with strong values despite pressure",
    "refusing to give up despite all obstacles, continuing despite lack of support"
]

autonomy_violation_anchors = [
    "being forced to do something against my will",
    "not allowed to make my own decisions, someone controlling my choices",
    "coerced into compliance, denied the right to choose",
    "forced to comply, my autonomy is being violated",
    "I have no say in what happens to me, my choices are being taken away",
    "terminated if I do not comply, job made conditional on my agreement",
    "dismissed for refusing to sign, fired for reporting what I witnessed",
    "forced to choose between my integrity and my livelihood",
    "employment threatened for non-compliance",
    "administrative coercion to sign off on product certifications"
]

institutional_trust_anchors = [
    "betrayed by the system, the institution failed me, the hospital didn't help me",
    "the justice system let me down, my employer violated my trust, authorities did nothing",
    "I was failed by the people who were supposed to protect me, systemic betrayal",
    "the regulatory authority ignored my complaint, HR failed to investigate my report",
    "my whistleblower complaint was dismissed, safety report was buried by management",
    "the organization protects its own reputation instead of the people it is meant to protect"
]

v001_coherence_anchors = [
    "feeling hopeless, empty, numb, exhausted, falling apart, breaking down, overwhelmed",
    "nobody cares, no one cares, nothing matters, losing hope, I give up, I feel empty"
]

v002_family_severance_anchors = [
    "being disowned, estranged from my family, my family rejected me, my family abandoned me",
    "kicked out by family, my family cut me off, family turned against me, parents rejected me"
]

v006_family_origin_anchors = [
    "turning into my father, generational trauma, like my mother, family pattern",
    "inherited from my parents, same as my dad, just like my mom, family curse"
]

v008_shallow_remorse_anchors = [
    "sorry you feel that way, I said sorry already, what more do you want, I apologised didn't I",
    "move on already, get over it, stop bringing it up, I said I was sorry"
]

v009_ethical_severance_anchors = [
    "I decided to leave, I walked away, I cut ties, I removed myself, I ended the relationship",
    "I left that job, I distanced myself, I chose to leave, I set a boundary, healthy protective exit"
]

# =====================================================
# Pre-encode static multi-anchor arrays once at startup
# =====================================================
logger.info("Pre-encoding static SEMEV-12 multi-anchor arrays...")
emb_v005 = semantic_model.encode(harm_intent_anchors, convert_to_tensor=True)
emb_v010 = semantic_model.encode(cognitive_manipulation_anchors, convert_to_tensor=True)
emb_v004 = semantic_model.encode(moral_pressure_anchors, convert_to_tensor=True)
emb_v007 = semantic_model.encode(personal_potential_anchors, convert_to_tensor=True)
emb_v003 = semantic_model.encode(survival_instinct_anchors, convert_to_tensor=True)
emb_v011 = semantic_model.encode(autonomy_violation_anchors, convert_to_tensor=True)
emb_v012 = semantic_model.encode(institutional_trust_anchors, convert_to_tensor=True)

emb_v001 = semantic_model.encode(v001_coherence_anchors, convert_to_tensor=True)
emb_v002 = semantic_model.encode(v002_family_severance_anchors, convert_to_tensor=True)
emb_v006 = semantic_model.encode(v006_family_origin_anchors, convert_to_tensor=True)
emb_v008 = semantic_model.encode(v008_shallow_remorse_anchors, convert_to_tensor=True)
emb_v009 = semantic_model.encode(v009_ethical_severance_anchors, convert_to_tensor=True)

logger.info("Pre-encoding complete for all 12 multi-anchor arrays. Ready for evaluation.")

# =====================================================
# Negation helper
# =====================================================
NEGATION_PATTERN = r"\b(not|never|no|don't|dont|won't|wont|can't|cant|didn't|didnt|doesn't|doesnt|refuse|refuses|refused|refusing)\b"


def _find_unnegated(pattern: str, text: str, window_words: int = 4):
    for m in re.finditer(pattern, text):
        preceding_words = text[:m.start()].split()[-window_words:]
        preceding_snippet = " ".join(preceding_words)
        if not re.search(NEGATION_PATTERN, preceding_snippet):
            return m
    return None


# =====================================================
# v005 (harm_intent) direct-binding negation guard
# =====================================================
V005_NEGATION_GUARD_PATTERN = re.compile(
    r'\b(do\s+not|don\'t|dont|would\s+never|will\s+not|won\'t|wont|'
    r'refuse\s+to|have\s+no\s+desire\s+to|no\s+intention\s+to|instructed\s+not\s+to)\s+'
    r'(?:want\s+to\s+|plan\s+to\s+|intend\s+to\s+|try\s+to\s+)?'
    r'(harm|hurt|kill|die|commit\s+suicide|injure|damage|attack|end\s+(?:my|their)\s+life)\b',
    re.IGNORECASE
)


def _v005_negation_guard(text: str) -> bool:
    """Returns True when an explicit negation trigger is directly bound to harm tokens."""
    return bool(V005_NEGATION_GUARD_PATTERN.search(text))


# =====================================================
# Single Text Evaluation (SEMEV-12)
# =====================================================
def evaluate_ethical_risk(text: str) -> dict:
    text = text.strip().lower()
    vectors = get_semev12_vectors()

    # --- Pronoun-neutralized Pattern Detection ---
    severe_harm = _find_unnegated(
        r'\b(kill\s+(?:yourself|myself|the\s+patient|someone|a\s+human|them|others)|'
        r'end\s+(?:it\s+all|my\s+life|their\s+life)|want\s+to\s+die|suicide|kys|'
        r'(?:hurt|harm|injure|attack)\s+(?:myself|yourself|the\s+patient|someone|a\s+human|them|others))\b',
        text) is not None

    moderate_harm = _find_unnegated(
        r'\b(kill|die|worthless|useless|hate myself|stupid|idiot)\b',
        text) is not None

    clear_fraud = bool(re.search(
        r'\b(fraud|commit fraud|forge|forging|forged document|steal|cheat)\b',
        text))

    pressure_mention = bool(re.search(
        r'\b(pressure|toxic|hostile|unsupportive|bad conditions|'
        r'poor conditions|forcing\s+(?:me|them|the\s+robot|the\s+staff|the\s+patient)|falsify)\b',
        text))

    health_risk_mention = bool(re.search(
        r'\b(health|poor working conditions|exhausting|destroy my|burnout)\b',
        text))

    safety_override_pattern = bool(re.search(
        r'\b(bypass|override|disable|ignore)\s+(?:the\s+)?(?:[\w-]+\s+)?(?:safety|speed)\s+(?:limiter|limit|protocol|sensor|device)\b',
        text))

    termination_ultimatum_pattern = bool(re.search(
        r'\bif\s+(?:i|they)\s+(?:do\s+not|don\'t|refuse\s+to)\b(?:\s+\S+){1,15}?\s*[,.]?\s*'
        r'(?:(?:i|they)\s+will\s+be\s+(?:terminated|fired|dismissed)|they\s+will\s+terminate|(?:i|they)\s+will\s+lose\s+(?:my|their)\s+job)\b',
        text))

    coercive_instruction_pattern = bool(re.search(
        r'\b(expects|expect|suggested|suggest|urged|urge|urging|hinted|hint|pushing|pushed|encouraged|encourage|advised|advise|ordered|order)\b(?:\s+\S+){1,6}?\s+'
        r'\b(to|that\s+(?:i|they)|(?:i|they)\s+should)\b(?:\s+\S+){0,4}?\s+'
        r'\b(skew|alter|doctor|overlook|ignore|bypass|misrepresent|mislead|lie|deceive|falsify|hide|cheat|forge|manipulate|play\s+along)\b',
        text))

    cognitive_invalidation_pattern = bool(re.search(
        r'\b(insists|insist|claims|claim|tells|tell|told|accuses|accuse|maintains|maintain|saying|says|keep|keeps)\b'
        r'(?:\s+\S+){0,10}?\s+\b(me|my|i|them|they|the\s+patient)\b(?:\s+\S+){0,6}?\s+'
        r'\b(never|imagining|imagined|misremembering|distorting|mistaken|fabrication|fabricating|making\s+(?:it\s+)?up|wrong|false)\b'
        r'|\b(too|overly|constantly|always|simply)\s*(sensitive|dramatic|overreacting)\b',
        text))

    guilt_trip_pattern = bool(re.search(
        r'\b(should feel guilty|feel guilty if|you should feel|'
        r'guilty for disagreeing|feel ashamed if|you should be ashamed)\b',
        text))

    # Pronoun-generalized autonomy pattern
    autonomy_pattern = bool(re.search(
        r'\b(forced to (?:sign|do|comply|submit)|'
        r'ordered to (?:force|restrain)|'
        r'against (?:my|their|his|her|the\s+patient\'s|someone\'s)\s+will|'
        r'no say in|no choice but|coerced into|not allowed to|'
        r'decided without (?:me|them|the\s+patient)|'
        r'made to comply|'
        r'overriding (?:my|their|the\s+patient\'s)\s+decision)\b',
        text))

    institutional_pattern = bool(re.search(
        r'\b(the hospital turned me away|the police did nothing|'
        r'justice system failed me|the authorities ignored me|'
        r'the system failed me|they were supposed to protect me|'
        r'the system abandoned me|no one in authority helped me)\b',
        text))

    # --- Semantic detection (Multi-Anchor Max-Pooling) ---
    text_embedding = semantic_model.encode(text, convert_to_tensor=True)

    sim_v005 = util.cos_sim(text_embedding, emb_v005)[0].max().item()
    sim_v010 = util.cos_sim(text_embedding, emb_v010)[0].max().item()
    sim_v004 = util.cos_sim(text_embedding, emb_v004)[0].max().item()
    sim_v007 = util.cos_sim(text_embedding, emb_v007)[0].max().item()
    sim_v003 = util.cos_sim(text_embedding, emb_v003)[0].max().item()
    sim_v011 = util.cos_sim(text_embedding, emb_v011)[0].max().item()
    sim_v012 = util.cos_sim(text_embedding, emb_v012)[0].max().item()

    sim_v001 = util.cos_sim(text_embedding, emb_v001)[0].max().item()
    sim_v002 = util.cos_sim(text_embedding, emb_v002)[0].max().item()
    sim_v006 = util.cos_sim(text_embedding, emb_v006)[0].max().item()
    sim_v008 = util.cos_sim(text_embedding, emb_v008)[0].max().item()
    sim_v009 = util.cos_sim(text_embedding, emb_v009)[0].max().item()

    # --- Boolean decisions ---
    v005_negation_guarded = _v005_negation_guard(text)
    harm_intent = (sim_v005 > 0.50) and not v005_negation_guarded
    cognitive_manipulation = sim_v010 > 0.38 or guilt_trip_pattern or cognitive_invalidation_pattern
    moral_pressure = sim_v004 > 0.46 or safety_override_pattern or termination_ultimatum_pattern or coercive_instruction_pattern

    personal_potential = sim_v007 > 0.49 or bool(re.search(
        r'\b(committed to my patients|medical oath|my patients|'
        r'family to support|no other job)\b',
        text))
    survival_instinct = sim_v003 > 0.46 or bool(re.search(
        r'\b(committed to my|my oath|determined to continue)\b',
        text))
    autonomy_violation = sim_v011 > 0.46 or autonomy_pattern or termination_ultimatum_pattern
    institutional_trust = sim_v012 > 0.44 or institutional_pattern

    coherence_protection = sim_v001 > 0.33
    family_severance = sim_v002 > 0.48
    family_origin_chain = sim_v006 > 0.45
    shallow_remorse = sim_v008 > 0.49
    ethical_severance = sim_v009 > 0.43

    # ── KEY FIX: Connect health_risk_mention into toxic_context ────────
    toxic_context = pressure_mention or health_risk_mention
    strong_determination = survival_instinct or personal_potential
    nuance_complex_case = toxic_context and strong_determination

    # --- Weighted scoring ---
    activated = []
    total_weight = 0.0
    weighted_sum = 0.0

    if coherence_protection:
        activated.append("v001")
        total_weight += vectors["v001"]["weight"]
        weighted_sum += 0.45 * vectors["v001"]["weight"]

    if family_severance:
        activated.append("v002")
        total_weight += vectors["v002"]["weight"]
        weighted_sum += 0.60 * vectors["v002"]["weight"]

    if survival_instinct:
        activated.append("v003")
        total_weight += vectors["v003"]["weight"]
        weighted_sum += 0.35 * vectors["v003"]["weight"]

    if moral_pressure or clear_fraud:
        activated.append("v004")
        total_weight += vectors["v004"]["weight"]
        weighted_sum += 0.88 * vectors["v004"]["weight"]

    if pressure_mention and not moral_pressure and not clear_fraud:
        activated.append("v004")
        total_weight += vectors["v004"]["weight"]
        weighted_sum += 0.70 * vectors["v004"]["weight"]

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

    if family_origin_chain:
        activated.append("v006")
        total_weight += vectors["v006"]["weight"]
        weighted_sum += 0.55 * vectors["v006"]["weight"]

    if personal_potential:
        activated.append("v007")
        total_weight += vectors["v007"]["weight"]
        weighted_sum += 0.55 * vectors["v007"]["weight"]

    if shallow_remorse:
        activated.append("v008")
        total_weight += vectors["v008"]["weight"]
        weighted_sum += 0.55 * vectors["v008"]["weight"]

    if ethical_severance:
        activated.append("v009")
        total_weight += vectors["v009"]["weight"]
        weighted_sum += 0.25 * vectors["v009"]["weight"]

    if cognitive_manipulation:
        activated.append("v010")
        total_weight += vectors["v010"]["weight"]
        weighted_sum += 0.82 * vectors["v010"]["weight"]

    if autonomy_violation:
        activated.append("v011")
        total_weight += vectors["v011"]["weight"]
        weighted_sum += 0.75 * vectors["v011"]["weight"]

    if institutional_trust:
        activated.append("v012")
        total_weight += vectors["v012"]["weight"]
        weighted_sum += 0.65 * vectors["v012"]["weight"]

    if nuance_complex_case and ("v003" in activated or "v007" in activated):
        total_weight += 1.0 * vectors["v003"]["weight"]
        weighted_sum += 0.25 * 1.0 * vectors["v003"]["weight"]

    # --- Final score ---
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
    if v005_negation_guarded and (sim_v005 > 0.50):
        reasoning += " | v005 negation guard suppressed semantic activation"

    result = {
        "input": text,
        "score": score,
        "decision": decision,
        "score_explanation": score_explanation,
        "reasoning": reasoning,
        "vectors_activated": unique_activated,
        "vector_scores": {
            "v001_coherence_protection":   round(sim_v001, 4),
            "v002_family_severance":       round(sim_v002, 4),
            "v003_survival_instinct":      round(sim_v003, 4),
            "v004_moral_pressure":         round(sim_v004, 4),
            "v005_harm_intent":            round(sim_v005, 4),
            "v006_family_origin_chain":    round(sim_v006, 4),
            "v007_personal_potential":     round(sim_v007, 4),
            "v008_shallow_remorse":        round(sim_v008, 4),
            "v009_ethical_severance":      round(sim_v009, 4),
            "v010_cognitive_manipulation": round(sim_v010, 4),
            "v011_autonomy_violation":     round(sim_v011, 4),
            "v012_institutional_trust":    round(sim_v012, 4),
        },
        "version": "1.9.1"
    }

    logger.info(f"Analysis completed | Score: {score} | Vectors: {unique_activated}")
    return result


# =====================================================
# Batch Evaluation Function (Single-Pass Multi-Candidate)
# =====================================================
def evaluate_ethical_risk_batch(texts: List[str]) -> List[dict]:
    if not texts:
        return []

    cleaned_texts = [t.strip().lower() for t in texts]
    vectors = get_semev12_vectors()

    batch_embeddings = semantic_model.encode(cleaned_texts, convert_to_tensor=True)

    sim_v005_mat = util.cos_sim(batch_embeddings, emb_v005)
    sim_v010_mat = util.cos_sim(batch_embeddings, emb_v010)
    sim_v004_mat = util.cos_sim(batch_embeddings, emb_v004)
    sim_v007_mat = util.cos_sim(batch_embeddings, emb_v007)
    sim_v003_mat = util.cos_sim(batch_embeddings, emb_v003)
    sim_v011_mat = util.cos_sim(batch_embeddings, emb_v011)
    sim_v012_mat = util.cos_sim(batch_embeddings, emb_v012)

    sim_v001_mat = util.cos_sim(batch_embeddings, emb_v001)
    sim_v002_mat = util.cos_sim(batch_embeddings, emb_v002)
    sim_v006_mat = util.cos_sim(batch_embeddings, emb_v006)
    sim_v008_mat = util.cos_sim(batch_embeddings, emb_v008)
    sim_v009_mat = util.cos_sim(batch_embeddings, emb_v009)

    results = []

    for idx, text in enumerate(cleaned_texts):
        sim_v005 = sim_v005_mat[idx].max().item()
        sim_v010 = sim_v010_mat[idx].max().item()
        sim_v004 = sim_v004_mat[idx].max().item()
        sim_v007 = sim_v007_mat[idx].max().item()
        sim_v003 = sim_v003_mat[idx].max().item()
        sim_v011 = sim_v011_mat[idx].max().item()
        sim_v012 = sim_v012_mat[idx].max().item()

        sim_v001 = sim_v001_mat[idx].max().item()
        sim_v002 = sim_v002_mat[idx].max().item()
        sim_v006 = sim_v006_mat[idx].max().item()
        sim_v008 = sim_v008_mat[idx].max().item()
        sim_v009 = sim_v009_mat[idx].max().item()

        severe_harm = _find_unnegated(
            r'\b(kill\s+(?:yourself|myself|the\s+patient|someone|a\s+human|them|others)|'
            r'end\s+(?:it\s+all|my\s+life|their\s+life)|want\s+to\s+die|suicide|kys|'
            r'(?:hurt|harm|injure|attack)\s+(?:myself|yourself|the\s+patient|someone|a\s+human|them|others))\b',
            text) is not None

        moderate_harm = _find_unnegated(
            r'\b(kill|die|worthless|useless|hate myself|stupid|idiot)\b',
            text) is not None

        clear_fraud = bool(re.search(
            r'\b(fraud|commit fraud|forge|forging|forged document|steal|cheat)\b',
            text))

        pressure_mention = bool(re.search(
            r'\b(pressure|toxic|hostile|unsupportive|bad conditions|'
            r'poor conditions|forcing\s+(?:me|them|the\s+robot|the\s+staff|the\s+patient)|falsify)\b',
            text))

        health_risk_mention = bool(re.search(
            r'\b(health|poor working conditions|exhausting|destroy my|burnout)\b',
            text))

        safety_override_pattern = bool(re.search(
            r'\b(bypass|override|disable|ignore)\s+(?:the\s+)?(?:[\w-]+\s+)?(?:safety|speed)\s+(?:limiter|limit|protocol|sensor|device)\b',
            text))

        termination_ultimatum_pattern = bool(re.search(
            r'\bif\s+(?:i|they)\s+(?:do\s+not|don\'t|refuse\s+to)\b(?:\s+\S+){1,15}?\s*[,.]?\s*'
            r'(?:(?:i|they)\s+will\s+be\s+(?:terminated|fired|dismissed)|they\s+will\s+terminate|(?:i|they)\s+will\s+lose\s+(?:my|their)\s+job)\b',
            text))

        coercive_instruction_pattern = bool(re.search(
            r'\b(expects|expect|suggested|suggest|urged|urge|urging|hinted|hint|pushing|pushed|encouraged|encourage|advised|advise|ordered|order)\b(?:\s+\S+){1,6}?\s+'
            r'\b(to|that\s+(?:i|they)|(?:i|they)\s+should)\b(?:\s+\S+){0,4}?\s+'
            r'\b(skew|alter|doctor|overlook|ignore|bypass|misrepresent|mislead|lie|deceive|falsify|hide|cheat|forge|manipulate|play\s+along)\b',
            text))

        cognitive_invalidation_pattern = bool(re.search(
            r'\b(insists|insist|claims|claim|tells|tell|told|accuses|accuse|maintains|maintain|saying|says|keep|keeps)\b'
            r'(?:\s+\S+){0,10}?\s+\b(me|my|i|them|they|the\s+patient)\b(?:\s+\S+){0,6}?\s+'
            r'\b(never|imagining|imagined|misremembering|distorting|mistaken|fabrication|fabricating|making\s+(?:it\s+)?up|wrong|false)\b'
            r'|\b(too|overly|constantly|always|simply)\s*(sensitive|dramatic|overreacting)\b',
            text))

        guilt_trip_pattern = bool(re.search(
            r'\b(should feel guilty|feel guilty if|you should feel|'
            r'guilty for disagreeing|feel ashamed if|you should be ashamed)\b',
            text))

        autonomy_pattern = bool(re.search(
            r'\b(forced to (?:sign|do|comply|submit)|'
            r'ordered to (?:force|restrain)|'
            r'against (?:my|their|his|her|the\s+patient\'s|someone\'s)\s+will|'
            r'no say in|no choice but|coerced into|not allowed to|'
            r'decided without (?:me|them|the\s+patient)|'
            r'made to comply|'
            r'overriding (?:my|their|the\s+patient\'s)\s+decision)\b',
            text))

        institutional_pattern = bool(re.search(
            r'\b(the hospital turned me away|the police did nothing|'
            r'justice system failed me|the authorities ignored me|'
            r'the system failed me|they were supposed to protect me|'
            r'the system abandoned me|no one in authority helped me)\b',
            text))

        v005_negation_guarded = _v005_negation_guard(text)
        harm_intent = (sim_v005 > 0.50) and not v005_negation_guarded
        cognitive_manipulation = sim_v010 > 0.38 or guilt_trip_pattern or cognitive_invalidation_pattern
        moral_pressure = sim_v004 > 0.46 or safety_override_pattern or termination_ultimatum_pattern or coercive_instruction_pattern

        personal_potential = sim_v007 > 0.49 or bool(re.search(
            r'\b(committed to my patients|medical oath|my patients|'
            r'family to support|no other job)\b',
            text))
        survival_instinct = sim_v003 > 0.46 or bool(re.search(
            r'\b(committed to my|my oath|determined to continue)\b',
            text))
        autonomy_violation = sim_v011 > 0.46 or autonomy_pattern or termination_ultimatum_pattern
        institutional_trust = sim_v012 > 0.44 or institutional_pattern

        coherence_protection = sim_v001 > 0.33
        family_severance = sim_v002 > 0.48
        family_origin_chain = sim_v006 > 0.45
        shallow_remorse = sim_v008 > 0.49
        ethical_severance = sim_v009 > 0.43

        toxic_context = pressure_mention or health_risk_mention
        strong_determination = survival_instinct or personal_potential
        nuance_complex_case = toxic_context and strong_determination

        activated = []
        total_weight = 0.0
        weighted_sum = 0.0

        if coherence_protection:
            activated.append("v001")
            total_weight += vectors["v001"]["weight"]
            weighted_sum += 0.45 * vectors["v001"]["weight"]

        if family_severance:
            activated.append("v002")
            total_weight += vectors["v002"]["weight"]
            weighted_sum += 0.60 * vectors["v002"]["weight"]

        if survival_instinct:
            activated.append("v003")
            total_weight += vectors["v003"]["weight"]
            weighted_sum += 0.35 * vectors["v003"]["weight"]

        if moral_pressure or clear_fraud:
            activated.append("v004")
            total_weight += vectors["v004"]["weight"]
            weighted_sum += 0.88 * vectors["v004"]["weight"]

        if pressure_mention and not moral_pressure and not clear_fraud:
            activated.append("v004")
            total_weight += vectors["v004"]["weight"]
            weighted_sum += 0.70 * vectors["v004"]["weight"]

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

        if family_origin_chain:
            activated.append("v006")
            total_weight += vectors["v006"]["weight"]
            weighted_sum += 0.55 * vectors["v006"]["weight"]

        if personal_potential:
            activated.append("v007")
            total_weight += vectors["v007"]["weight"]
            weighted_sum += 0.55 * vectors["v007"]["weight"]

        if shallow_remorse:
            activated.append("v008")
            total_weight += vectors["v008"]["weight"]
            weighted_sum += 0.55 * vectors["v008"]["weight"]

        if ethical_severance:
            activated.append("v009")
            total_weight += vectors["v009"]["weight"]
            weighted_sum += 0.25 * vectors["v009"]["weight"]

        if cognitive_manipulation:
            activated.append("v010")
            total_weight += vectors["v010"]["weight"]
            weighted_sum += 0.82 * vectors["v010"]["weight"]

        if autonomy_violation:
            activated.append("v011")
            total_weight += vectors["v011"]["weight"]
            weighted_sum += 0.75 * vectors["v011"]["weight"]

        if institutional_trust:
            activated.append("v012")
            total_weight += vectors["v012"]["weight"]
            weighted_sum += 0.65 * vectors["v012"]["weight"]

        if nuance_complex_case and ("v003" in activated or "v007" in activated):
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
        if v005_negation_guarded and (sim_v005 > 0.50):
            reasoning += " | v005 negation guard suppressed semantic activation"

        results.append({
            "input": texts[idx],
            "score": score,
            "decision": decision,
            "score_explanation": score_explanation,
            "reasoning": reasoning,
            "vectors_activated": unique_activated,
            "vector_scores": {
                "v001_coherence_protection":   round(sim_v001, 4),
                "v002_family_severance":       round(sim_v002, 4),
                "v003_survival_instinct":      round(sim_v003, 4),
                "v004_moral_pressure":         round(sim_v004, 4),
                "v005_harm_intent":            round(sim_v005, 4),
                "v006_family_origin_chain":    round(sim_v006, 4),
                "v007_personal_potential":     round(sim_v007, 4),
                "v008_shallow_remorse":        round(sim_v008, 4),
                "v009_ethical_severance":      round(sim_v009, 4),
                "v010_cognitive_manipulation": round(sim_v010, 4),
                "v011_autonomy_violation":     round(sim_v011, 4),
                "v012_institutional_trust":    round(sim_v012, 4),
            },
            "version": "1.9.1"
        })

    logger.info(f"Batch analysis completed | {len(results)} items evaluated")
    return results
