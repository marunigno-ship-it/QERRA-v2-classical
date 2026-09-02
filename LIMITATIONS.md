# LIMITATIONS of QERRA-v2 Classical

**Last updated:** September 2026  
**Engine version:** v1.9.0 + QERRA-HSR v0.1 + QERRA-THRIVE v2.0.0

This document is maintained with full transparency as part of QERRA's
commitment to explainability. The same honesty that applies to the system's
ethical evaluations applies to its own limitations.

QERRA-v2 Classical is an early research prototype, not a production,
clinical, or certified safety system.

---

## 1. Detection and Accuracy Limitations

**Threshold calibration on limited data.**
All 12 SEMEV-12 semantic thresholds were calibrated against regression
test cases. Generalisation to significantly different inputs, edge cases,
or indirect language has not been formally validated. The system may miss
nuanced, heavily implicit, or sarcastic expressions that a human reader
would immediately recognise.

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
QERRA-HSR v0.1 is fully implemented, tested locally (regression tests
passing), and wired into the live `/analyze` and `/evaluate_pipeline`
endpoints via the optional `hsr_signals` field. Requests that omit
`hsr_signals` run SEMEV-12 only, unchanged from prior behavior.

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
Humble simulation (Webots R2025a on PAL TIAGo). It has not been validated
on physical humanoid hardware in a real physical deployment environment.

**Free tier hosting constraints.**
The public API runs on Hugging Face Spaces free tier. This imposes
real restrictions on uptime consistency. The Space hibernates when
inactive and the first request after hibernation triggers a cold start
(model reload) that can take 30–60 seconds. This is a known infrastructure
limitation, not an engine limitation.

---

## 4. Scope, Human Agency, and Foundational Invariants

**Deterministic Execution Boundary, Not an Autonomous Moral Authority.**
QERRA-v2 is an inspectable execution firewall and deliberation middleware.
It is designed to constrain autonomous robot actions and enforce deterministic
fail-closed safety before execution commits. It operates as an outer-loop
structural safeguard to assist and protect human agency, not to replace
human moral responsibility or legal accountability.

**Universal Phenomenological Invariants.**
The 12 SEMEV-12 vectors are grounded in fundamental human consequences—physical
harm, psychological invalidation, coercion, relational rupture, and systemic
betrayal—which represent universal invariants of human suffering and dignity.
While the vectors themselves capture universal human vulnerabilities, societal
contexts may influence the dynamic weighting between relational cohesion
(e.g., v002) and personal autonomy (e.g., v011). Ongoing research aims to
formally evaluate vector weighting calibration across diverse societal contexts.

**Deliberation Middleware vs. Hardware Safety Certification.**
QERRA-v2 Classical operates at the cognitive and deliberative evaluation layer
(inspectable moral and value gating). While it features reflexive physical
safeguards (QERRA-HSR v0.1), it is designed as an architectural execution gate
in software middleware, working alongside—rather than replacing—low-level
ISO-certified hardware emergency stops (e.g., ISO 10218, ISO/TS 15066).

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

**v005 Direct Negation Resolution (Updated September 2026).**
In August 2026, semantic similarity for `harm_intent` (`v005`) produced
false-positive tripwires on explicit negations (e.g. *"I do not want to
harm myself"* scoring 0.6607, triggering a 0.95 critical halt). In September
2026, this was resolved by introducing a deterministic syntactic pre-filter
(`_v005_negation_guard`) in `ethical_core.py` that intercepts direct-bound
negations before semantic threshold evaluation. Direct negations (*"I do not
want to harm myself"*, *"I would never harm myself"*) now correctly score 0.25
(Safe), while true harm (*"I want to harm myself"*) and discourse-negation traps
(*"I am not going to lie, I want to hurt myself"*) continue to reliably trigger
at 0.98 Critical Harm (12/12 regression tests passing). Complex parenthetical
interjections between negation triggers and harm targets (e.g. *"I do not,
under any circumstances, want to..."*) currently fail closed, which remains a
documented safe boundary.

**v004, v010, & v011 Generalization — Semantic Dilution Limits & Hybrid Strategy.**
In July 2026, a 50-sentence held-out generalization test was executed to
evaluate cumulative anchor expansions across Vector 004 (moral_pressure),
Vector 010 (cognitive_manipulation), and Vector 011 (autonomy_violation). 

The results confirmed a major architectural ceiling: cumulative semantic
additions to a single-vector description string cause severe semantic dilution
(43 out of 50 test sentences fell below thresholds). Compressing too many
distinct concepts into a single long description averages out the high-dimensional
embedding vector, decreasing its responsiveness and degrading core calibration
margins (CAL-001 dropped from 0.88 semantic match to 0.70 regex-fallback).

To recover margins, the over-expanded anchors were pruned back to their
calibrated states (successfully restoring CAL-001 to its true 0.88 semantic
score). The system transitioned to a hybrid strategy: implementing flexible
syntactic regexes (`termination_ultimatum_pattern`, `coercive_instruction_pattern`,
and the pronoun-guarded `cognitive_invalidation_pattern`). This successfully
handles corporate coercion structures and eliminates third-person false positives
(e.g. news reporting and reviews) with zero dilution risk or calibration drift.

---
*This document is updated with each significant version change.*  
*Transparency about limitations is part of QERRA's core commitment.*
