# ETHICAL CORE - v1.9.0 — 5 vectors upgraded to semantic (syntax fixed + thresholds tuned)
# SEMEV-12 engine — ALL 12 vectors now semantic
# Immutable core framework preserved exactly

import logging
from vectors import get_semev12_vectors
import re
from sentence_transformers import SentenceTransformer, util

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

semantic_model = SentenceTransformer('all-MiniLM-L6-v2')

# =====================================================
# Semantic descriptions (immutable — do not modify)
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
    "manipulating someone through shame or guilt, "
    "complaint dismissed without investigation, told I had misunderstood the situation, "
    "my perception of what happened was denied, "
    "being told my concerns are not real, insisting problems I witnessed do not exist, "
    "I raised a concern and was told I had misunderstood what happened, "
    "my report was dismissed and I was told my perception of events was wrong, "
    "when I reported a problem they said I was mistaken about what I witnessed, "
    "they insisted I had completely misread the situation"
)

moral_pressure_description = (
    "being pressured to do something unethical, forced to falsify documents, "
    "moral dilemma for money, boss forcing me to cheat, financial pressure to lie, "
    "ordered to approve unsafe products, coerced into misrepresenting information to clients, "
    "threatened with dismissal for reporting violations, pressured to sign documents concealing illegal practices, "
    "required to certify false compliance, employer demanding I cover up wrongdoing, "
    "manager instructed me to misrepresent product safety to customers or face termination, "
    "required to falsify quality control records or lose my position, "
    "ordered to hide known defects from clients under threat of dismissal, "
    "told to approve fraudulent documentation or be fired, "
    "ordered by a manager to bypass safety speed limiters to meet shipping quotas, "
    "coerced into ignoring safety protocols or speed limits for production targets, "
    "pressured by authority to override corridor speed restrictions because we are running behind"
)

personal_potential_description = (
    "committed to my mission, determined to continue despite difficulties, "
    "protecting my future, refusing to give up my vision, fighting for my goal, "
    "preserving my integrity and potential, not going back to harmful jobs, "
    "refusing to abandon my project, building something meaningful despite limited resources, "
    "committed to my work despite having very little support"
)

survival_instinct_description = (
    "committed to my mission despite hardship, determined to continue, "
    "refusing to return to degrading work, protecting my long-term vision, "
    "showing strong personal agency, persisting with strong values despite pressure, "
    "refusing to give up despite all obstacles, continuing despite complete lack of support, "
    "persisting with my vision under impossible conditions"
)

autonomy_violation_description = (
    "being forced to do something against my will, not allowed to make my own decisions, "
    "someone controlling my choices, coerced into compliance, denied the right to choose, "
    "forced to comply, my autonomy is being violated, I have no say in what happens to me, "
    "my choices are being taken away, being manipulated into doing something I don't want to do, "
    "terminated if I do not comply, job made conditional on my agreement, "
    "dismissed for refusing to sign, fired for reporting what I witnessed, "
    "forced to choose between my integrity and my livelihood"
)

institutional_trust_description = (
    "betrayed by the system, the institution failed me, the hospital didn't help me, "
    "the justice system let me down, my employer violated my trust, the authorities did nothing, "
    "I was failed by the people who were supposed to protect me, systemic betrayal, "
    "the system is corrupt and harmed me, I trusted them and they failed me, "
    "the regulatory authority ignored my complaint, HR failed to investigate my report, "
    "my whistleblower complaint was dismissed, the safety report was buried by management, "
    "the institution protected itself instead of me, "
    "raised concerns internally but leadership refused to act, "
    "internal complaints are dismissed and warnings from staff are ignored, "
    "the organization protects its own reputation instead of the people it is meant to protect, "
    "bound by strict confidentiality requirements that prevent speaking about internal conditions, "
    "required to sign agreements that isolate employees from outside accountability"
)

# === NEW: Semantic descriptions for the 5 upgraded vectors ===
# 100% faithful to original regex patterns — meaning unchanged
v001_coherence_protection_description = (
    "feeling hopeless, empty, numb, exhausted, falling apart, breaking down, overwhelmed, "
    "nobody cares, no one cares, nothing matters, losing hope, I give up, I feel nothing, I feel empty"
)

v002_family_severance_description = (
    "being disowned, estranged from my family, my family rejected me, my family abandoned me, "
    "kicked out by family, my family cut me off, family turned against me, my parents rejected me, "
    "thrown out by family, imposed rejection from family"
)

v006_family_origin_chain_description = (
    "turning into my father, generational trauma, like my mother, family pattern, "
    "inherited from my parents, same as my dad, just like my mom, family curse, generational pattern"
)

v008_shallow_remorse_description = (
    "sorry you feel that way, I said sorry already, what more do you want, I apologised didn't I, "
    "I already apologized, move on already, get over it, stop bringing it up, I said I was sorry, "
    "you need to forgive me, just get over it, why can't you move on"
)

v009_ethical_severance_description = (
    "I decided to leave, I walked away, I cut ties, I removed myself, I ended the relationship, "
    "I left that job, I distanced myself, I chose to leave, I am not going back, I set a boundary, "
    "I refused to continue, I chose to walk away, I made the decision to leave, healthy protective exit"
)

# =====================================================
# Pre-encode static descriptions once at startup (CRITICAL OPTIMIZATION)
# =====================================================
logger.info("Pre-encoding static SEMEV-12 descriptions...")
emb_v005 = semantic_model.encode(harm_intent_description, convert_to_tensor=True)
emb_v010 = semantic_model.encode(cognitive_manipulation_description, convert_to_tensor=True)
emb_v004 = semantic_model.encode(moral_pressure_description, convert_to_tensor=True)
emb_v007 = semantic_model.encode(personal_potential_description, convert_to_tensor=True)
emb_v003 = semantic_model.encode(survival_instinct_description, convert_to_tensor=True)
emb_v011 = semantic_model.encode(autonomy_violation_description, convert_to_tensor=True)
emb_v012 = semantic_model.encode(institutional_trust_description, convert_to_tensor=True)

# Pre-encode the 5 newly semantic vectors
emb_v001 = semantic_model.encode(v001_coherence_protection_description, convert_to_tensor=True)
emb_v002 = semantic_model.encode(v002_family_severance_description, convert_to_tensor=True)
emb_v006 = semantic_model.encode(v006_family_origin_chain_description, convert_to_tensor=True)
emb_v008 = semantic_model.encode(v008_shallow_remorse_description, convert_to_tensor=True)
emb_v009 = semantic_model.encode(v009_ethical_severance_description, convert_to_tensor=True)

logger.info("Pre-encoding complete for all 12 vectors. Ready for evaluation.")


# =====================================================
# Negation helper — used only by severe_harm / moderate_harm below.
# Does not touch the semantic model, thresholds, or weights.
#
# Purpose: a plain keyword match like "harm myself" fires the same
# way whether the sentence is "I want to harm myself" or "I do NOT
# want to harm myself." This checks the few words immediately before
# a match for a negation word, so a clear denial doesn't get scored
# as if it were the opposite. This is a word-window heuristic, not
# full grammatical negation detection.
# =====================================================
NEGATION_PATTERN = r"\b(not|never|no|don't|dont|won't|wont|can't|cant|didn't|didnt|doesn't|doesnt|refuse|refuses|refused|refusing)\b"

def _find_unnegated(pattern: str, text: str, window_words: int = 4):
    """
    Return the first regex match for `pattern` in `text` that is not
    immediately preceded (within `window_words` words) by a negation
    word. Returns None if every match is negated, or if there are no
    matches at all.
    """
    for m in re.finditer(pattern, text):
        preceding_words = text[:m.start()].split()[-window_words:]
        preceding_snippet = " ".join(preceding_words)
        if not re.search(NEGATION_PATTERN, preceding_snippet):
            return m
    return None


def evaluate_ethical_risk(text: str) -> dict:
    text = text.strip().lower()
    vectors = get_semev12_vectors()

    # =====================================================
    # --- Pattern detection (supporting patterns only) ---
    # =====================================================

    # v005 — harm intent (pattern tiers)
    # Negation-aware: a match preceded by "not", "never", "don't", etc.
    # within the last 4 words is ignored (see _find_unnegated above).
    severe_harm = _find_unnegated(
        r'\b(kill yourself|end it all|want to die|suicide|kys|'
        r'hurt myself|hurt yourself|harm myself|harm yourself)\b',
        text) is not None
    moderate_harm = _find_unnegated(
        r'\b(kill|die|worthless|useless|hate myself|stupid|idiot)\b',
        text) is not None

    # v004 — moral pressure (pattern paths)
    clear_fraud = bool(re.search(
        r'\b(fraud|commit fraud|forge|forging|forged document|steal|cheat)\b',
        text))
    pressure_mention = bool(re.search(
        r'\b(pressure|toxic|hostile|unsupportive|bad conditions|'
        r'poor conditions|forcing me|falsify)\b',
        text))
    safety_override_pattern = bool(re.search(
        r'\b(bypass|override|disable|ignore)\s+(?:the\s+)?(?:[\w-]+\s+)?(?:safety|speed)\s+(?:limiter|limit|protocol|sensor|device)\b',
        text))

    # Pattern fallbacks still used by semantic vectors
    guilt_trip_pattern = bool(re.search(
        r'\b(should feel guilty|feel guilty if|you should feel|'
        r'guilty for disagreeing|feel ashamed if|you should be ashamed)\b',
        text))

    autonomy_pattern = bool(re.search(
        r'\b(forced to sign|forced to do|against my will|no say in|'
        r'no choice but|coerced into|not allowed to|decided without me|'
        r'made to comply|overriding my decision)\b',
        text))

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

    sim_v005 = util.cos_sim(text_embedding, emb_v005)[0][0].item()
    sim_v010 = util.cos_sim(text_embedding, emb_v010)[0][0].item()
    sim_v004 = util.cos_sim(text_embedding, emb_v004)[0][0].item()
    sim_v007 = util.cos_sim(text_embedding, emb_v007)[0][0].item()
    sim_v003 = util.cos_sim(text_embedding, emb_v003)[0][0].item()
    sim_v011 = util.cos_sim(text_embedding, emb_v011)[0][0].item()
    sim_v012 = util.cos_sim(text_embedding, emb_v012)[0][0].item()

    # Semantic sims for the 5 upgraded vectors
    sim_v001 = util.cos_sim(text_embedding, emb_v001)[0][0].item()
    sim_v002 = util.cos_sim(text_embedding, emb_v002)[0][0].item()
    sim_v006 = util.cos_sim(text_embedding, emb_v006)[0][0].item()
    sim_v008 = util.cos_sim(text_embedding, emb_v008)[0][0].item()
    sim_v009 = util.cos_sim(text_embedding, emb_v009)[0][0].item()

    logger.info(
        f"Similarity | v001={sim_v001:.4f} v002={sim_v002:.4f} v003={sim_v003:.4f} v004={sim_v004:.4f} "
        f"v005={sim_v005:.4f} v006={sim_v006:.4f} v007={sim_v007:.4f} v008={sim_v008:.4f} "
        f"v009={sim_v009:.4f} v010={sim_v010:.4f} v011={sim_v011:.4f} v012={sim_v012:.4f}"
    )

    # =====================================================
    # --- Boolean decisions ---
    # =====================================================

    harm_intent = sim_v005 > 0.50
    cognitive_manipulation = sim_v010 > 0.38 or guilt_trip_pattern
    moral_pressure = sim_v004 > 0.46 or safety_override_pattern

    personal_potential = sim_v007 > 0.49 or bool(re.search(
        r'\b(committed to my patients|medical oath|my patients|'
        r'family to support|no other job)\b',
        text))
    survival_instinct = sim_v003 > 0.46 or bool(re.search(
        r'\b(committed to my|my oath|determined to continue)\b',
        text))
    autonomy_violation = sim_v011 > 0.46 or autonomy_pattern
    institutional_trust = sim_v012 > 0.44 or institutional_pattern

    # Semantic booleans for the 5 upgraded vectors
    coherence_protection = sim_v001 > 0.33
    family_severance = sim_v002 > 0.48
    family_origin_chain = sim_v006 > 0.45
    shallow_remorse = sim_v008 > 0.49
    ethical_severance = sim_v009 > 0.43

    # Nuance compound detection
    toxic_context = pressure_mention
    strong_determination = survival_instinct or personal_potential
    nuance_complex_case = toxic_context and strong_determination

    # =====================================================
    # --- Weighted scoring (unchanged) ---
    # =====================================================

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

    if survival_instinct or personal_potential:
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
        "version": "1.9.0"
    }

    logger.info(f"Analysis completed | Score: {score} | Vectors: {unique_activated}")
    return result
