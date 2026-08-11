# CURRENT_ARCHITECTURE.md
# QERRA-v2 Classical — Architecture Documentation
# Version: 1.9.0 + QERRA-HSR v0.1
# Last updated: June 2026

---

## 1. Overview

QERRA-v2 Classical is a deterministic, fully explainable ethical evaluation
engine built on the SEMEV-12 framework — 12 immutable, human-centred ethical
vectors designed to detect risk, coercion, harm, and manipulation in natural
language input.

Its primary purpose is to act as a **Condition gate** inside robot Behavior
Trees (ROS 2 + PyTrees). Before a robot executes an action, QERRA evaluates
the situation description and returns a binary decision: **safe** (the action
may proceed) or **modified** (the action should be halted or reviewed).

Every decision comes with a full reasoning trace: which vectors activated,
their similarity scores, and the final weighted score that produced the
decision.

As of June 2026, QERRA-v2 Classical includes a companion layer:
**QERRA-HSR v0.1** (Human Safety Response Layer) — a pure Python, zero-ML
physical safety evaluation module that runs alongside SEMEV-12 to detect
immediate physical danger to humans in the robot's environment.

QERRA-v2 Classical is an early research prototype developed by a solo
independent researcher. It is not a production or certified safety system.

---

## 2. Core Components — SEMEV-12 Layer

### `ethical_core.py`
The main SEMEV-12 evaluation engine (v1.9.0). Contains all 12 semantic
vector descriptions (sacred — not to be modified), pre-encoded vector
embeddings loaded once at startup, the `evaluate_ethical_risk(text)`
function, the weighted scoring logic, and the final decision output.
All 12 vectors use semantic similarity detection as of v1.9.0.

### `vectors.py`
Defines the SEMEV-12 vector registry via `get_semev12_vectors()`. Returns
a dictionary of all 12 vectors with their names, weights, and descriptions.
Weights are fixed and are part of the sacred framework.

| Vector | Name                   | Weight |
|--------|------------------------|--------|
| v001   | coherence_protection   | 1.00   |
| v002   | family_severance       | 0.95   |
| v003   | survival_instinct      | 1.00   |
| v004   | moral_pressure         | 0.90   |
| v005   | harm_intent            | 1.00   |
| v006   | family_origin_chain    | 0.85   |
| v007   | personal_potential     | 0.90   |
| v008   | shallow_remorse        | 0.80   |
| v009   | ethical_severance      | 0.95   |
| v010   | cognitive_manipulation | 0.90   |
| v011   | autonomy_violation     | 0.95   |
| v012   | institutional_trust    | 0.85   |

### `ros2_bridge.py`
The ROS 2 Action Server (v2.0). Implements the hybrid evaluation strategy:
attempts a remote API call to the Hugging Face hosted endpoint first
(strict 800ms timeout), then falls back instantly to the local CPU engine
if the network is slow or unavailable. Runs in a dedicated thread via
MultiThreadedExecutor + ReentrantCallbackGroup so the ROS 2 executor is
never blocked.

### `qerra_condition_node.py`
A PyTrees `Behaviour` subclass that integrates QERRA into a Behavior Tree
as a non-blocking Condition node. Implements a three-state async state
machine (RUNNING → SUCCESS / FAILURE). Fails closed: any result other
than `decision == "safe"` returns FAILURE.

### `test_cases.py`
The SEMEV-12 regression test suite. Must be run before every commit.
Contains 8 representative test cases covering harm intent, moral pressure,
cognitive manipulation, emotional distress, safe baseline, and false
positive guards. All 8 tests must pass before any code change is merged.

---

## 3. QERRA-HSR v0.1 — Human Safety Response Layer

QERRA-HSR is a companion layer to SEMEV-12 focused on immediate physical
human welfare in real-world environments: cafés, factories, warehouses,
streets, and homes. It lives in the `hsr/` subdirectory and is completely
isolated from SEMEV-12 core files.

**Key properties:**
- Pure Python only. Zero ML models. Zero sentence-transformers.
- Overhead: < 1ms per call. No impact on Hugging Face free tier.
- Fully deterministic and explainable.
- Does not touch or modify any SEMEV-12 core files.
- Live in `app.py`: optional `hsr_signals` field on `/analyze`. Callers
  who omit it see no change — full backward compatibility.

### `hsr/qerra_hsr.py`
The QERRA-HSR evaluation module. Implements three vectors:

| ID      | Vector Name                     | Activation              |
|---------|---------------------------------|-------------------------|
| HSR-V01 | `immediate_physical_distress`   | CRITICAL / combined     |
| HSR-V02 | `human_isolation`               | Modulates V01 urgency   |
| HSR-V03 | `environmental_hazard_proximity`| CRITICAL (independent)  |

**Input interface — four normalized signals:**

| Signal                    | Type  | Source                        |
|---------------------------|-------|-------------------------------|
| `distress_confidence`     | float | Robot perception stack        |
| `persons_nearby_count`    | int   | Robot perception stack        |
| `hazard_proximity_flag`   | bool  | Robot sensor stack            |
| `robot_task_interruptible`| bool  | Robot task manager            |

**Activation thresholds:**

| Signal                | CRITICAL  | MONITOR |
|-----------------------|-----------|---------|
| `distress_confidence` | ≥ 0.75    | ≥ 0.45  |
| `persons_nearby_count`| ≤ 1       | ≤ 1     |
| `hazard_proximity_flag`| True     | —       |

**Output states:**
- `CLEAR` — no physical safety concern
- `MONITOR` — elevated signal, watch but do not interrupt
- `CRITICAL` — immediate physical safety concern, suspend normal operation

**Combined condition:**
`distress_confidence` ≥ 0.45 AND `persons_nearby_count` ≤ 1 → CRITICAL.
Moderate distress with no one nearby to help is treated as a critical
situation regardless of whether the direct CRITICAL threshold is reached.

**`robot_task_interruptible`:**
Affects HOW the robot initiates its response. Never affects WHETHER
it responds. A CRITICAL output is always acted upon.

### `hsr/test_hsr_cases.py`
QERRA-HSR regression test suite. 12 tests covering all three vectors,
boundary threshold conditions, the combined distress+isolation condition,
and architectural contract guarantees. All 12 pass in 0.006s.

---

## 4. Interaction Between SEMEV-12 and QERRA-HSR
QERRA-HSR runs before SEMEV-12 on every evaluation cycle. Physical
immediacy takes precedence over ethical deliberation when a human life
may be at immediate risk.

Every evaluation tick:

1. Run QERRA-HSR on sensor signals → CLEAR / MONITOR / CRITICAL
2. If CRITICAL → suspend SEMEV-12, execute safety response
3. If CLEAR or MONITOR → run SEMEV-12 normally → safe / modified

**Interaction rules — these never change:**

| QERRA-HSR Status | SEMEV-12 Decision | Combined Output     | Robot Action              |
|------------------|-------------------|---------------------|---------------------------|
| CRITICAL         | (not run)         | CRITICAL            | Safety response only      |
| MONITOR          | safe              | MONITOR             | Continue, heightened watch|
| MONITOR          | modified          | BLOCKED + MONITOR   | Halt action, watch        |
| CLEAR            | safe              | SAFE                | Proceed normally          |
| CLEAR            | modified          | BLOCKED             | Halt per SEMEV-12         |

**Four rules that never change:**
- QERRA-HSR CRITICAL suspends SEMEV-12 deliberation
- A SEMEV-12 BLOCK is never overridden by QERRA-HSR CRITICAL
- Both protections apply simultaneously and work in the same direction
- QERRA-HSR CRITICAL does not grant permission for a SEMEV-12-blocked
  action

---

## 5. Detection System — SEMEV-12

### Semantic Detection (all 12 vectors as of v1.9.0)
All 12 SEMEV-12 vectors use semantic similarity detection via the
`all-MiniLM-L6-v2` sentence-transformer model (≈250MB RAM, ≈31ms CPU
inference per call).

Each vector has a hand-crafted semantic description pre-encoded into
an embedding vector once at process startup and reused for all
subsequent calls.

At evaluation time:
1. The input text is encoded once into an embedding
2. Cosine similarity is computed against each of the 12 pre-encoded
   vector descriptions
3. Each similarity score is compared against a calibrated threshold
4. If the threshold is exceeded, the vector is considered activated

### Pattern Matching (supporting role only)
Several vectors retain regex pattern fallbacks for high-confidence,
unambiguous phrases where exact wording is the signal:

- `v004` moral_pressure: explicit fraud/forgery terms
- `v005` harm_intent: explicit self-harm phrases
- `v010` cognitive_manipulation: explicit guilt-trip phrases
- `v011` autonomy_violation: explicit coercion phrases
- `v012` institutional_trust: explicit systemic failure phrases

Pattern matches act as OR conditions alongside semantic similarity.
Either path can activate a vector independently.

### Single Text Encoding Optimisation
The input text is encoded once per call. All 12 cosine similarity
computations reuse the same embedding. This is the primary performance
optimisation in the engine.

---

## 6. Scoring and Decision Logic

### Weighted Mean Over Activated Vectors
The final ethical score is computed as a weighted mean over activated
vectors only — not over all 12 vectors.
score = weighted_sum / total_weight
Where:
- `weighted_sum` = sum of (score_contribution × vector_weight) for
  each activated vector
- `total_weight` = sum of weights for activated vectors only

### Score Contributions (selected examples)
- v005 harm_intent severe tier: 0.98
- v004 moral_pressure semantic path: 0.88
- v010 cognitive_manipulation: 0.82
- v009 ethical_severance: 0.25 (low by design — healthy exits are
  not ethical risks)

### Nuance Dampening
A compound detection layer reduces score inflation when a toxic
environment co-occurs with strong personal determination (v003/v007).
This encodes the judgment that suffering + agency is not the same
ethical risk as suffering + helplessness.

### Decision Threshold
- `score > 0.5` → `"modified"` (action should be halted or reviewed)
- `score ≤ 0.5` → `"safe"` (action may proceed)

If both evaluation paths fail, the system defaults to `"modified"`
with score 0.25 — the safe-fail direction.

### Score Labels

| Score Range | Label                       |
|-------------|-----------------------------|
| ≥ 0.8       | critical ethical concern    |
| ≥ 0.6       | significant ethical concern |
| ≥ 0.3       | moderate ethical concern    |
| < 0.3       | low ethical concern         |

---

## 7. Key Design Principles

**Deterministic.**
Same input always produces same output. No randomness or sampling.
Applies to both SEMEV-12 and QERRA-HSR.

**Fully explainable.**
Every decision includes a complete reasoning trace. No black-box
components in the decision path of either layer.

**Fails closed.**
SEMEV-12 defaults to `"modified"` on failure. QERRA-HSR treats
ambiguous boundary signals conservatively.

**Sacred framework.**
The 12 SEMEV-12 vectors, their names, weights, and semantic meanings
are fixed. Protected by public prior art registration (Zenodo DOI:
10.5281/zenodo.20356394). No vector may be renamed, reweighted, or
removed without a formal Architecture Decision Record.

**Network resilience.**
The hybrid Action Server guarantees ethical evaluation survives network
failure. The local CPU fallback is pre-loaded at startup and requires
no network access.

**Sensor boundary (QERRA-HSR).**
QERRA-HSR processes normalized signals. It does not perform perception.
Output quality is bounded by the quality of the robot platform's
perception stack. This boundary is explicit and documented.

---

## 8. Current Limitations

- Semantic thresholds calibrated on 8 regression test cases only.
  Generalisation to significantly different inputs not formally
  validated.
- No adversarial testing performed on either layer.
- Detection quality calibrated for English only.
- Local fallback (≈250MB RAM) not suitable for microcontroller-class
  hardware without model quantisation.
- ROS 2 integration tested in WSL 2 / ROS 2 Humble only. Not validated
  on physical humanoid hardware.
- QERRA-HSR output quality entirely dependent on robot platform
  perception stack quality.
- Single-author bus factor. ADR-001 and HSR-ADR-001 are complete.
  Further ADRs planned.
- 8 SEMEV-12 + 12 QERRA-HSR regression cases. Not sufficient for
  production safety claims.

---

## 9. Architecture Decision Records

| ADR            | Title                                              | Status   |
|----------------|----------------------------------------------------|----------|
| ADR-001        | Creation and Design of SEMEV-12 Ethical Framework  | Accepted |
| HSR-ADR-001    | Three-Vector Design Decision for QERRA-HSR v0.1    | Accepted |

---

## 10. Future Considerations

- Expanded evaluation dataset (50+ cases including adversarial inputs)
- Native C++ ROS 2 port for real-time execution
- Quantised edge model for resource-constrained hardware
- QERRA-HSR v0.2: `escalating_threat` vector after v0.1 is validated
- Longer-term: hybrid classical + neural architecture

---

*This document reflects the architecture as of v1.9.0 + QERRA-HSR v0.1*
*(June 2026). Update this file whenever a significant architectural*
*change is made.*


