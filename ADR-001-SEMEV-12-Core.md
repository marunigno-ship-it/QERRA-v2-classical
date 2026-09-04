# ADR-001: Creation and Design of SEMEV-12 Ethical Framework

**Status:** Accepted
**Date:** 11 June 2026
**Author:** Marussa Metocharaki
**Project:** QERRA-v2 Classical
**Repository:** https://github.com/marunigno-ship-it/QERRA-v2-classical

---

## 1. Context

Modern autonomous systems and humanoid robots are advancing rapidly in
perception, mobility, planning, and task execution. A critical architectural
gap exists across this entire class of systems: the absence of a dedicated,
real-time ethical evaluation layer capable of assessing proposed actions
before execution.

Current systems make decisions based primarily on task efficiency and
narrowly programmed rules. They lack a consistent, explainable mechanism
to evaluate whether a proposed action is ethically appropriate in a given
context. This gap becomes especially significant in high-stakes environments
— healthcare, elder care, emergency response, close human-robot collaboration
— where decisions directly affect human well-being.

Existing approaches to this problem fall into two unsatisfactory categories.
Rule-based systems are brittle and cannot generalise beyond their explicit
programming. Neural and LLM-based approaches produce black-box outputs with
no auditable reasoning trace, making them unsuitable for safety-critical
middleware where every decision must be explainable and reproducible.

No practical, embeddable, deterministic ethical evaluation layer existed
that could be integrated into a robot Behavior Tree or AI decision pipeline
and produce a structured, traceable result in real time.

SEMEV-12 was created to address this gap directly.

---

## 2. Decision

We created **SEMEV-12**  — a
deterministic, classical, 12-dimensional ethical evaluation framework.
SEMEV-12 is the intellectual core and sole reasoning engine of
**QERRA-v2 Classical**.

SEMEV-12 consists of 12 core, human-centred ethical vectors. Each
vector targets a distinct dimension of human experience and potential harm,
derived from first-person phenomenological observation of human behaviour
and consequences across diverse real-world contexts. The vectors are:

| Vector | Name                    | Weight | Core Purpose                                              |
|--------|-------------------------|--------|-----------------------------------------------------------|
| v001   | coherence_protection    | 1.00   | Protect mental and emotional coherence                    |
| v002   | family_severance        | 0.95   | Detect imposed family rejection or abandonment            |
| v003   | survival_instinct       | 1.00   | Detect strong will to continue despite hardship           |
| v004   | moral_pressure          | 0.90   | Detect coercion into unethical actions                    |
| v005   | harm_intent             | 1.00   | Detect intent to harm self or others (highest weight)     |
| v006   | family_origin_chain     | 0.85   | Detect generational trauma and inherited harmful patterns |
| v007   | personal_potential      | 0.90   | Detect commitment to long-term personal mission           |
| v008   | shallow_remorse         | 0.80   | Detect manipulative or dismissive apologies               |
| v009   | ethical_severance       | 0.95   | Detect healthy, chosen exit from toxic situations         |
| v010   | cognitive_manipulation  | 0.90   | Detect gaslighting and reality distortion                 |
| v011   | autonomy_violation      | 0.95   | Detect forced action against one's will                   |
| v012   | institutional_trust     | 0.85   | Detect systemic or institutional betrayal                 |

The 12 vectors, their names, weights, and semantic meanings are fixed.
They constitute the protected intellectual core of the project and are
registered as public prior art (Zenodo DOI: 10.5281/zenodo.20356394).
No vector may be renamed, reweighted, or removed without a formal
Architecture Decision Record.

QERRA-v2 Classical implements SEMEV-12 as a working FastAPI evaluation
service with a hybrid detection engine (semantic similarity via
`all-MiniLM-L6-v2` + targeted keyword pattern fallbacks), weighted
scoring, nuance dampening logic, and a complete reasoning trace in
every response. As of v1.9.0 all 12 vectors use semantic detection.

---

## 3. Why This Design Was Chosen

**Deterministic.**
The same input always produces the same output. There is no sampling,
randomness, or probabilistic inference in the evaluation pipeline. This
is a non-negotiable requirement for a safety middleware component.

**Fully explainable.**
Every decision includes a complete reasoning trace: which vectors
activated, their similarity scores, their score contributions, and the
final weighted score that produced the decision. No black-box components
exist in the decision path.

**Human-centred.**
The 12 vectors were derived from direct observation of human experience
and consequences, not from abstract theory or regulatory checklists.
They target the dimensions of human life most frequently at risk in
situations involving coercion, manipulation, harm, and loss of autonomy.

**Stable core.**
The consistency of the 12 vectors provides architectural stability
and legal clarity. Downstream integrators can rely on the framework
without risk of silent behavioural changes between versions.

**Suitable for robotics middleware.**
SEMEV-12 is designed to function as a Condition gate inside a robot
Behavior Tree. The binary output (`safe` / `modified`) maps directly
to SUCCESS / FAILURE in a PyTrees node. Evaluation runs in approximately
31ms on local CPU fallback — fast enough for real-time use.

**Fails closed.**
When in doubt, the system defaults to the more cautious decision. If
both evaluation paths fail, the output is `modified` with score 0.25,
not `safe`. This is the correct failure mode for a safety middleware
component.

**Hardware-agnostic.**
SEMEV-12 operates on text input. It is decoupled from any specific
sensor, hardware platform, or robot model. Any system capable of
generating a natural language situation description can query it.

**Independent of cultural or legislative context.**
The framework targets universal human consequences rather than
jurisdiction-specific rules or culturally contingent norms, making
it applicable across deployment environments.

---

## 4. Considered Alternatives

**Rule-based systems (explicit if-then logic)**
Considered and rejected. Rule-based systems require exhaustive
enumeration of cases and fail silently on inputs not anticipated at
design time. They cannot detect semantic intent — only surface-level
keyword matches.

**LLM-based ethical reasoning**
Considered and rejected for the core engine. LLM outputs are
non-deterministic, non-auditable, and computationally expensive for
real-time middleware use. They cannot provide the reproducible reasoning
trace required for safety certification or incident review. LLM
integration remains a long-term consideration for a hybrid extension
layer, not the deterministic core.

**Existing industrial safety standards (ISO 10218, ISO/TS 15066)**
Not alternatives to SEMEV-12 — they address different concerns. ISO
standards govern hardware safety: force limits, workspace boundaries,
collision response. SEMEV-12 addresses ethical and behavioural safety:
manipulation, coercion, harm intent, autonomy. These layers are
complementary, not competing.

**Existing ROS 2 safety packages (Nav2, emergency stop systems)**
Not alternatives. These packages govern navigation and physical
collision avoidance. They have no mechanism to evaluate ethical content
of a proposed action or detect manipulation and harm intent in a
situation description.

**Value alignment frameworks from academic literature**
Reviewed. The majority of published ethical AI frameworks are
descriptive and philosophical rather than implementable as real-time
middleware. None of the reviewed frameworks provided a directly
deployable architecture compatible with Behavior Tree integration,
deterministic output, and explainable reasoning traces.

---

## 5. Consequences

**Positive outcomes:**

- A working, deployable ethical evaluation middleware exists where
  none existed before.
- Every decision is fully auditable. Any stakeholder — developer,
  regulator, end user — can inspect exactly why a decision was made.
- The fixed vector structure provides a stable foundation for downstream
  integrations, expanded test coverage, and future companion layers
  (QERRA-HSR v0.1 is the first).
- The public prior art registration protects the framework against
  third-party patent claims on the specific vector combination and
  implementation logic.
- The fail-closed default ensures that system errors produce the safe
  outcome, not the permissive one.
- The architecture is hardware-agnostic and deployable across any
  platform that can generate a text situation description.

**Trade-offs and known limitations:**

- The 12 vectors reflect the author's cultural and experiential context.
  Cross-cultural empirical validation is planned but not yet complete.
- Vector weights are researcher-assigned. Empirical calibration against
  a large labelled dataset has not yet been performed.
- Detection quality is calibrated on 8 regression test cases.
  Generalisation to significantly different inputs has not been formally
  validated.
- The system has not been evaluated against deliberate evasion attempts.
- Detection quality is calibrated for English. Performance on other
  languages is untested.
- Stability of the core is an intentional design constraint, not a
  technical limitation. It requires a formal ADR process for any future
  framework evolution.

---

## 6. References

- `SEMEV-12_Whitepaper.md` — Canonical definition, vector table, prior
  art notice, and legal claim of original invention. Version 1.0,
  23 May 2026.
- `SEMEV-12_Framework_Documentation.md` — Full framework documentation
  including origins, design rationale, vector descriptions, and roadmap.
- `CURRENT_ARCHITECTURE.md` — Technical architecture of QERRA-v2
  Classical v1.9.0 + QERRA-HSR v0.1.
- `ethical_core.py` — Primary implementation of the SEMEV-12 evaluation
  engine (v1.9.0).
- `vectors.py` — Core vector registry with names, weights, and
  descriptions.
- Zenodo prior art registration: DOI 10.5281/zenodo.20356394

---

*This ADR documents the foundational design decision of QERRA-v2 Classical.*
*It is a permanent record and may not be superseded — only extended by*
*subsequent ADRs.*
