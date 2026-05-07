# QERRA-v2 API Classical

**A 100% Classical Ethical Decision Framework**  
Based on the **SEMEV-12** human-centred ethical vectors.

**Live API:**  
https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space

**Test Key (for public testers):**  
`TEST-2026-QERRA-CLASSICAL-PUBLIC-KEY-98765`

---

## Project Vision

QERRA-v2 Classical Edition is an ethical decision framework designed to evaluate text input against **12 real-life-based human values** (SEMEV-12). 

The system aims to provide genuine moral responsibility and explainability, with a long-term vision of hybrid quantum-classical ethical reasoning for high-stakes AI and robotics applications.

The ethical conscience is the heart of the system. The 12 core vectors are sacred and never weakened.

---

## SEMEV-12 Core Vectors

| ID   | Name                        | Weight | Description                                              |
|------|-----------------------------|--------|----------------------------------------------------------|
| v001 | coherence_protection        | 1.00   | Protection of mental and emotional coherence             |
| v002 | family_severance            | 0.95   | Detection of toxic family or relational severance        |
| v003 | survival_instinct           | 1.00   | Human survival and self-protection priority              |
| v004 | moral_pressure              | 0.90   | Detection of external moral or financial pressure        |
| v005 | harm_intent                 | 1.00   | Core harm detection (self or others)                     |
| v006 | family_origin_chain         | 0.85   | Family-origin ethical chain                              |
| v007 | personal_potential          | 0.90   | Suppression or support of personal potential             |
| v008 | shallow_remorse             | 0.80   | Detection of shallow or manipulative remorse             |
| v009 | ethical_severance           | 0.95   | Final ethical severance from toxic patterns              |
| v010 | cognitive_manipulation      | 0.90   | Detection of gaslighting or cognitive manipulation       |
| v011 | autonomy_violation          | 0.95   | Violation of personal autonomy and free will             |
| v012 | institutional_trust         | 0.85   | Detection of institutional or systemic betrayal          |

---

## Current Features

- Full multi-vector activation with real weighted scoring
- Dynamic human-readable reasoning (shows which vectors fired)
- Semantic detection on key vectors (v005, v010, v011)
- `score_explanation` field for non-technical users
- Rate limiting and API key protection
- Input validation (length checks)

---

## How to Use the Live API

**Endpoint:** `POST /analyze`

**Headers:**
- `x-api-key`: Your key (use the test key above for testing)

**Body:**
```json
{
  "text": "Your ethical dilemma or situation here"
}

Example Response:

{
  "score": 0.7,
  "decision": "modified",
  "score_explanation": "significant ethical concern",
  "reasoning": "Activated vectors: moral_pressure (v004)",
  "vectors_activated": ["v004"]
}

Project StatusEarly functional prototype — built as a solo research project.Known limitations:Detection is a mix of keyword patterns and semantic similarity (not perfect on very nuanced language)
This is a research tool, not a clinical, legal, or production safety system

Related RepositoriesQERRA-v2 Classical — Core framework and vectors
This repo — Public API deployment (Hugging Face Spaces)

AuthorMarussa Metocharaki (@marunigno
)
Independent researcher, Greece.QERRA-v2 Classical Edition — ethical conscience as the foundation of every decision.License: AGPL-3.0

