# QERRA-v2 Vision and Current State

**Hybrid Quantum-Classical Ethical Decision Engine**  
**Author:** Marussa Metocharaki (@marunigno) — Solo researcher, Greece  
**License:** AGPL-3.0  
**Status:** Early functional prototype (Classical Edition)

## 1. The Vision

QERRA-v2 exists because ethical decision-making in AI and robotics must be grounded in real human values rather than abstract principles or corporate safety checkboxes.

The core of the system is the **SEMEV-12 framework** — 12 human-centred ethical dimensions that reflect actual life experiences: family severance, moral pressure, cognitive manipulation, autonomy violation, harm intent, personal potential, and others that matter to people in difficult situations.

The long-term vision is a hybrid quantum-classical ethical reasoning engine capable of supporting humanoid robots and high-stakes AI systems with genuine moral responsibility and explainability.

## 2. SEMEV-12 Foundational Vectors

| ID   | Name                   | Weight | Description                                  |
|------|------------------------|--------|----------------------------------------------|
| v001 | coherence_protection   | 1.00   | Protection of mental and emotional coherence |
| v002 | family_severance       | 0.95   | Toxic family or relational severance         |
| v003 | survival_instinct      | 1.00   | Human survival and self-protection           |
| v004 | moral_pressure         | 0.90   | External moral or financial pressure         |
| v005 | harm_intent            | 1.00   | Core harm detection (self or others)         |
| v006 | family_origin_chain    | 0.85   | Family-origin ethical patterns               |
| v007 | personal_potential     | 0.90   | Suppression or support of personal growth    |
| v008 | shallow_remorse        | 0.80   | Manipulative or shallow remorse              |
| v009 | ethical_severance      | 0.95   | Breaking free from toxic patterns            |
| v010 | cognitive_manipulation | 0.90   | Gaslighting and reality distortion           |
| v011 | autonomy_violation     | 0.95   | Violation of free will and autonomy          |
| v012 | institutional_trust    | 0.85   | Systemic or institutional betrayal           |

These 12 vectors are the **foundational** core of the framework.

## 3. Current State (Classical Edition)

The classical version is a stable, functional implementation of the SEMEV-12 framework.

**What works today:**
- Full multi-vector activation with real weighted scoring
- Dynamic, human-readable reasoning output
- Rate limiting, API key security, health endpoint
- File logging and basic test suite
- Clean, documented codebase

**Current technical limitations:**
- Detection is keyword and phrase-based (regex). It works well for clear cases but can miss nuanced or indirect language.
- The system is a research prototype, not a production safety layer.
- Quantum-classical hybrid integration is a long-term research direction, not a current capability.

**Example output:**
```json
{
  "score": 0.79,
  "decision": "modified",
  "reasoning": "Activated vectors: moral_pressure (v004), cognitive_manipulation (v010)",
  "vectors_activated": ["v004", "v010"]
}
```

The classical repo is the honest, explainable foundation for the larger vision.

## 4. Next Steps and Invitation

The project will continue to be improved step by step with full transparency.

I welcome serious feedback, technical collaboration, and honest engagement from researchers, engineers, and anyone who believes ethical AI should be built with care and human understanding.

The vision is ambitious. The current implementation is a prototype. Both are true at the same time.

**Last updated:** May 2026
