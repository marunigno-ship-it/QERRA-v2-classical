# HSR-ADR-001: Three-Vector Design Decision for QERRA-HSR v0.1

**Status:** Accepted
**Date:** 12 June 2026
**Author:** Marussa Metocharaki
**Project:** QERRA-v2 Classical — QERRA Human Safety Response Layer
**Repository:** https://github.com/marunigno-ship-it/QERRA-v2-classical

---

## 1. Context

SEMEV-12 handles deliberative ethical reasoning over natural language input:
manipulation, coercion, harm intent, autonomy violation, institutional
betrayal. These are slow, contextual concerns that require semantic
understanding of what is being said or requested.

A critical complementary gap existed: no layer addressed immediate,
acute physical human welfare in the robot's physical environment. When
a person near a robot collapses, when a hazard is about to cause injury,
when someone is alone and in distress — these situations require a fast,
interrupt-level response that SEMEV-12 was not designed to provide,
because they are not expressed in language. They are expressed in
sensor signals.

QERRA-HSR was created to close this gap as a deterministic, lightweight
companion layer — architecturally separate from SEMEV-12, working
alongside it, never in conflict with it.

The question this ADR answers is: **which vectors should QERRA-HSR v0.1
implement, and why exactly these and no others?**

---

## 2. Decision

QERRA-HSR v0.1 implements exactly **three vectors**:

| ID      | Name                          | Priority               |
|---------|-------------------------------|------------------------|
| HSR-V01 | `immediate_physical_distress` | CRITICAL trigger       |
| HSR-V02 | `human_isolation`             | HIGH — modulates V01   |
| HSR-V03 | `environmental_hazard_proximity` | HIGH — independent trigger |

No additional vectors will be added to v0.1 without a new ADR.

---

## 3. Why These Three Vectors

**HSR-V01 — `immediate_physical_distress`**
The foundational vector. Without it the layer has no purpose. It
processes a normalized `distress_confidence` float (0.0–1.0) from the
robot's perception stack. QERRA-HSR does not determine what is medically
wrong — it responds to a signal, not a diagnosis. Activation threshold:
`distress_confidence` ≥ 0.75 for direct CRITICAL. Also activates via
the combined condition with HSR-V02 (see Section 5).

**HSR-V02 — `human_isolation`**
Makes the response intelligent rather than reflexive. A person collapsing
in a crowded café is a different situation from a person collapsing alone
in a warehouse at night. The robot's obligation changes depending on
whether other humans are present and able to help. Without this vector
the layer treats all distress situations identically — which is both
inefficient and potentially disruptive in real deployment. Activates
when `persons_nearby_count` ≤ 1 with any active distress signal.

**HSR-V03 — `environmental_hazard_proximity`**
Extends coverage to robot-adjacent dangers that may not yet have caused
visible distress. Reflects a distinct moral responsibility: the robot's
own operation can create or exacerbate danger. Activates independently
of HSR-V01 — a confirmed hazard near a human is a CRITICAL condition
on its own, before any distress is visible. Activates when
`hazard_proximity_flag` is True.

---

## 4. Why `escalating_threat` Was Excluded from v0.1

An `escalating_threat` vector was considered and deliberately excluded.

Detecting that an interpersonal argument is about to become violent
requires social inference — tone, body language, proximity patterns,
interaction history — that produces a high false positive rate in real
environments. A robot that incorrectly intervenes in a heated but
non-violent conversation is a liability, not a safety asset.

The three vectors in v0.1 activate on normalized numeric and boolean
inputs with high reliability. `escalating_threat` cannot meet this bar
in v0.1. It is a candidate for v0.2 after v0.1 has been validated in
practice.

---

## 5. Activation Logic

### Input Interface

| Signal | Type | Source |
|---|---|---|
| `distress_confidence` | float 0.0–1.0 | Robot perception stack |
| `persons_nearby_count` | int | Robot perception stack |
| `hazard_proximity_flag` | bool | Robot sensor stack or task monitor |
| `robot_task_interruptible` | bool | Robot task manager |

### Activation Thresholds

| Signal | CRITICAL threshold | MONITOR threshold |
|---|---|---|
| `distress_confidence` | ≥ 0.75 | ≥ 0.45 |
| `persons_nearby_count` (isolation) | ≤ 1 | ≤ 1 |
| `hazard_proximity_flag` | True | — |

### CRITICAL fires if ANY one condition is met:
- `distress_confidence` ≥ 0.75
- `hazard_proximity_flag` is True
- `distress_confidence` ≥ 0.45 AND `persons_nearby_count` ≤ 1
  (combined condition — moderate distress + isolation)

### MONITOR fires if:
- `distress_confidence` ≥ 0.45
- AND none of the CRITICAL conditions are met

### `robot_task_interruptible`
Affects HOW the robot initiates its response. Never affects WHETHER
it responds. A CRITICAL output is always acted upon.

---

## 6. The Sensor Boundary

QERRA-HSR processes signals. It does not produce them.

The robot's perception stack is responsible for computing
`distress_confidence`, counting `persons_nearby_count` (upright,
responsive humans only — a distressed person does not count toward
this total), setting `hazard_proximity_flag`, and reporting
`robot_task_interruptible`.

QERRA-HSR output quality is bounded by input signal quality. This
boundary is explicit and must be stated clearly in all deployment
documentation.

---

## 7. Interaction with SEMEV-12

QERRA-HSR runs before SEMEV-12 on every evaluation cycle.

Every evaluation tick:

1. Run QERRA-HSR on sensor signals → CLEAR / MONITOR / CRITICAL
2. If CRITICAL → suspend SEMEV-12, execute safety response
3. If CLEAR or MONITOR → run SEMEV-12 normally

**Four rules that never change:**
- QERRA-HSR CRITICAL suspends SEMEV-12 deliberation
- A SEMEV-12 BLOCK is never overridden by QERRA-HSR CRITICAL
- Both protections apply simultaneously and work in the same direction
- QERRA-HSR CRITICAL does not grant permission for a SEMEV-12-blocked
  action

---

## 8. Implementation Status

| Component | Status |
|---|---|
| `hsr/__init__.py` | Complete |
| `hsr/qerra_hsr.py` | Complete — pure Python, zero ML |
| `hsr/test_hsr_cases.py` | Complete — 12 regression tests, all passing |
| API integration (`app.py`) | Planned — next implementation step |

**Performance:** 12 tests complete in 0.006s. Overhead < 1ms per call.
Hugging Face free tier compatible.

---

## 9. Consequences

**Positive:**
- Minimal implementation scope — three vectors, pure Python, no ML
  models, no additional dependencies beyond Python standard library.
- Zero RAM and latency overhead added to the existing deployment.
- Clear, deterministic interaction rules with SEMEV-12.
- The sensor boundary is explicitly defined — QERRA-HSR makes no
  claims about perception quality.
- 12 regression tests cover all vectors, boundary conditions, the
  combined distress+isolation condition, and architectural contract
  guarantees.

**Trade-offs:**
- v0.1 does not cover interpersonal threat escalation.
- All activation thresholds are design estimates pending empirical
  validation against real or simulated deployment data.
- Output reliability is entirely dependent on the robot platform's
  perception stack quality.

---

## 10. References

- `hsr/qerra_hsr.py` — Complete implementation (v0.1)
- `hsr/test_hsr_cases.py` — Regression test suite (12 tests)
- `QERRA-HSR-Design-v0.1.md` — Full proposed design document
- `ADR-001-SEMEV-12-Core.md` — SEMEV-12 foundational design decision
- `CURRENT_ARCHITECTURE.md` — Full system architecture documentation
- Zenodo prior art: DOI 10.5281/zenodo.20356394

---

*This ADR documents the three-vector design decision for QERRA-HSR v0.1.*
*Any change to the vector set after implementation requires a new ADR.*
*This record is permanent and may not be superseded — only extended.*   

## 7. Interaction with SEMEV-12

QERRA-HSR runs before SEMEV-12 on every evaluation cycle.
