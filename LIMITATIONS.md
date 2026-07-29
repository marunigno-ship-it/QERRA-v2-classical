# LIMITATIONS of QERRA-v2 Classical

**Last updated:** June 2026
**Engine version:** v1.9.0 + QERRA-HSR v0.1

This document is maintained with full transparency as part of QERRA's
commitment to explainability. The same honesty that applies to the system's
ethical evaluations applies to its own limitations.

QERRA-v2 Classical is an early research prototype, not a production,
clinical, or certified safety system.

---

## 1. Detection and Accuracy Limitations

**Threshold calibration on limited data.**
All 12 SEMEV-12 semantic thresholds were calibrated against 8 regression
test cases. This is a small sample. Generalisation to significantly
different inputs, edge cases, or indirect language has not been formally
validated. The system may miss nuanced, heavily implicit, or sarcastic
expressions that a human reader would immediately recognise.

**No adversarial robustness testing.**
The system has not been evaluated against deliberate evasion attempts —
paraphrasing, code-switching, indirect language, or adversarial inputs
designed to avoid detection. A motivated actor could likely construct
inputs that bypass detection.

**Language scope.**
Detection quality is calibrated for English. Performance on other
languages is untested and likely significantly degraded. The semantic
model (`all-MiniLM-L6-v2`) has multilingual capability but QERRA's
vector descriptions and pattern fallbacks are English-only.

**Researcher-assigned weights.**
Vector weights and score contributions reflect the author's judgment
based on observation of human experience. They have not been empirically
validated against a large labelled dataset. Empirical calibration is
planned but not yet performed.

---

## 2. QERRA-HSR Physical Safety Layer Limitations

**Sensor dependency.**
QERRA-HSR v0.1 processes normalized signals from the robot's perception
stack. It does not perform sensing itself. Output quality is entirely
bounded by the quality of the robot platform's perception stack. A
platform with poor fall detection will produce poor QERRA-HSR outcomes
regardless of the layer's internal logic.

**Activation thresholds are design estimates.**
The three thresholds (`distress_confidence` ≥ 0.75 for CRITICAL,
≥ 0.45 for MONITOR, `persons_nearby_count` ≤ 1 for isolation) are
design estimates, not empirically validated values. They must be
calibrated against real or simulated deployment data before any
deployment claim is made.

**Integrated into the live API.**
QERRA-HSR v0.1 is fully implemented, tested locally (12 regression
tests passing), and wired into the live `/analyze` endpoint via the
optional `hsr_signals` field. Requests that omit `hsr_signals` run
SEMEV-12 only, unchanged from prior behavior.

**Interpersonal threat detection is out of scope for v0.1.**
Detecting that an interpersonal situation is escalating toward violence
requires social inference with a high false positive rate in real
environments. This vector (`escalating_threat`) was deliberately excluded
from v0.1 and is a candidate for a future version after v0.1 is validated.

---

## 3. System Architecture Limitations

**Single-author bus factor.**
QERRA-v2 Classical is developed and maintained by one independent
researcher. Architectural rationale and calibration history are
documented in ADRs but the depth of institutional knowledge remains
concentrated in a single person.

**Hardware scope.**
The local CPU fallback (≈250MB RAM for `all-MiniLM-L6-v2`) is not
suitable for microcontroller-class hardware without model quantisation.
Edge deployment on resource-constrained hardware requires a quantised
model variant not yet produced.

**Physical robot deployment.**
The ROS 2 integration has been compiled and tested in WSL 2 / ROS 2
Humble. It has not been validated on physical humanoid hardware in a
real deployment environment.

**Free tier hosting constraints.**
The public API runs on Hugging Face Spaces free tier. This imposes
real restrictions on uptime consistency. The Space hibernates when
inactive and the first request after hibernation triggers a cold start
(model reload) that can take 30–60 seconds. This is a known infrastructure
limitation, not an engine limitation.

---

## 4. Scope and Ethical Boundaries

**Not a substitute for professional judgment.**
QERRA-v2 is a research and integration tool. It is not a substitute for
professional human judgment, clinical assessment, legal advice, or
certified safety systems. Any output should be treated as one structured
input among many, not as a final decision.

**Cultural context.**
The 12 SEMEV-12 vectors were derived from the author's personal
observations and experiences. They reflect a particular cultural and
experiential context. Cross-cultural empirical validation is planned
but not yet performed. The framework is offered as a hypothesis open
to broader review and refinement.

**Not a certified safety system.**
Neither SEMEV-12 nor QERRA-HSR constitutes a certified safety system
under any applicable standard (ISO 10218, ISO/TS 15066, IEC 61508, or
equivalent). They operate at the deliberation and ethical reasoning
layer, not the hardware safety layer.

---

## 5. Known Technical Notes

**v001 detection scope.**
The `coherence_protection` vector detects emotional distress signals
and threats to psychological coherence. Its semantic description is
calibrated for direct first-person expressions. Indirect or
third-person descriptions of distress may fall below the activation
threshold (0.33).

**v009 intentionally low score contribution.**
`ethical_severance` has a score contribution of 0.25 by design.
Healthy, chosen exits from toxic situations are not ethical risks —
they are protective acts. The low contribution reflects this judgment.

**Nuance dampening scope.**
The compound nuance logic (toxic environment + strong personal
determination) applies only when both `pressure_mention` and
`survival_instinct` or `personal_potential` are active simultaneously.
It does not generalise to other compound cases.

**v005 negation near threshold.**
The semantic similarity score for harm_intent (v005) does not reliably
encode negation. Testing against the live API showed "I do not want to
harm myself" scoring 0.51 — just above the 0.50 activation threshold —
while "I would never harm myself" scored 0.41, correctly below it. This
is a known limitation of sentence-embedding models generally: negated
and non-negated phrasings of the same core content can produce very
similar embeddings. A fix was applied and verified for the regex
fallback checks (severe_harm, moderate_harm), but the underlying
semantic similarity score itself is not currently corrected for
negation. Planned: a structured negation test set, similar in approach
to the SEMEV-12 Benchmark Run, before any further changes to this
behavior.

**v004, v010, & v011 Generalization — Semantic Dilution Limits & Hybrid Strategy.**
In July 2026, a 50-sentence held-out generalization test was executed to evaluate cumulative anchor expansions across Vector 004 (moral_pressure), Vector 010 (cognitive_manipulation), and Vector 011 (autonomy_violation). 

The results confirmed a major architectural ceiling: cumulative semantic additions to a single-vector description string cause severe semantic dilution (43 out of 50 test sentences fell below thresholds). Compressing too many distinct concepts into a single long description averages out the high-dimensional embedding vector, decreasing its responsiveness and degrading core calibration margins (CAL-001 dropped from 0.88 semantic match to 0.70 regex-fallback).

To recover margins, the over-expanded anchors were pruned back to their calibrated states (successfully restoring CAL-001 to its true 0.88 semantic score). The system transitioned to a hybrid strategy: implementing a flexible syntactic regex (`termination_ultimatum_pattern`) into the boolean logic paths. This successfully handles logical corporate coercion structures with zero dilution risk or calibration drift.
*This document is updated with each significant version change.*
*Transparency about limitations is part of QERRA's core commitment.*
