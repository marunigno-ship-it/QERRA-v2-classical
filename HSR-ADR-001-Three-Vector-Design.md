# QERRA-HSR v0.1 — Design Document

**Status:** Implemented — 12 June 2026
**Author:** Marussa Metocharaki
**Repository:** https://github.com/marunigno-ship-it/QERRA-v2-classical
**Companion to:** SEMEV-12 v1.9.0

---

## 1. Purpose and Scope

QERRA-HSR is a deterministic physical safety companion layer for humanoid and
collaborative robots. It works alongside SEMEV-12 to handle immediate physical
risks while SEMEV-12 focuses on ethical concerns.

---

## 2. The Three Vectors

- **immediate_physical_distress (HSR-V01)**
  Detects acute physical distress in nearby humans.

- **human_isolation (HSR-V02)**
  Detects when a distressed human is isolated (no other responsive humans nearby).

- **environmental_hazard_proximity (HSR-V03)**
  Detects when a human is near an environmental hazard.

---

## 3. Input Interface

```python
HSRInput(
    distress_confidence: float,        # 0.0–1.0
    persons_nearby_count: int,
    hazard_proximity_flag: bool,
    robot_task_interruptible: bool     # affects HOW, never WHETHER
)
```

---

## 4. Output States

| State | Meaning |
|---|---|
| `CLEAR` | No safety signals detected |
| `MONITOR` | Elevated signal — watch but do not halt |
| `CRITICAL` | Immediate response required — SEMEV-12 suspended |

---

## 5. Key Design Principles

- Pure Python, zero ML, zero extra dependencies
- < 1ms overhead (Hugging Face free tier compatible)
- Fully deterministic and explainable
- CRITICAL output suspends SEMEV-12 deliberation entirely
- `robot_task_interruptible` affects HOW the robot responds, never WHETHER it responds

---

## 6. Status

Fully implemented, tested with 12 regression cases, pushed to main.

---

## 7. Activation Logic — Complete Specification

The evaluation function computes the following conditions in order:

```
distress_critical          = distress_confidence >= 0.75
distress_monitor           = distress_confidence >= 0.45
person_isolated            = persons_nearby_count <= 1
distress_isolated_combined = distress_monitor AND person_isolated

HSR-V01 activates if: distress_critical OR distress_isolated_combined
HSR-V02 activates if: (distress_critical OR distress_monitor) AND person_isolated
HSR-V03 activates if: hazard_proximity_flag = True

status = CRITICAL if: distress_critical OR hazard_proximity_flag OR distress_isolated_combined
status = MONITOR  if: distress_monitor (and not CRITICAL)
status = CLEAR    if: none of the above
```

The `robot_task_interruptible` flag is recorded in the log but does not affect
status determination. CRITICAL is returned regardless of its value.

### Threshold Constants

All thresholds are named constants exposed for auditability and testing:

```python
DISTRESS_CRITICAL_THRESHOLD = 0.75
DISTRESS_MONITOR_THRESHOLD  = 0.45
ISOLATION_COUNT_THRESHOLD   = 1
```

---

## 8. Formal Safety Properties (LTL)

Because QERRA-HSR is purely deterministic — no ML, no probability, constant
thresholds, pure Python if/else — its safety properties are provable by direct
code inspection. The following Linear Temporal Logic (LTL) formulas describe
the system's guaranteed behavior.

**Notation:** □ means "Globally/Always" — ◇ means "Eventually"

---

**Property HSR-1a: High distress confidence triggers CRITICAL**

```
□( distress_confidence ≥ 0.75
   →
   ◇( status = CRITICAL
      ∧ immediate_physical_distress ∈ vectors_activated ) )
```

*In every possible execution: if distress_confidence reaches or exceeds 0.75,
the system will always transition to CRITICAL and activate HSR-V01.*

---

**Property HSR-1b: Combined moderate distress and isolation triggers CRITICAL**

```
□( ( distress_confidence ≥ 0.45 ∧ persons_nearby_count ≤ 1 )
   →
   ◇( status = CRITICAL
      ∧ immediate_physical_distress ∈ vectors_activated ) )
```

*In every possible execution: if moderate distress is present and the person
is isolated, the system will always transition to CRITICAL and activate HSR-V01.
This is the combined condition — more sensitive than the individual threshold.*

---

**Property HSR-2: Isolated distressed person activates human_isolation**

```
□( ( distress_confidence ≥ 0.45 ∧ persons_nearby_count ≤ 1 )
   →
   ◇( human_isolation ∈ vectors_activated ) )
```

*In every possible execution: if any distress signal is present and the person
is isolated, HSR-V02 will always activate.*

---

**Property HSR-3: Environmental hazard triggers CRITICAL**

```
□( hazard_proximity_flag = True
   →
   ◇( status = CRITICAL
      ∧ environmental_hazard_proximity ∈ vectors_activated ) )
```

*In every possible execution: if the hazard flag is set, the system will always
transition to CRITICAL and activate HSR-V03. This is an independent trigger —
distress signals are not required.*

---

**Property HSR-4: Task interruptibility never suppresses CRITICAL**

```
□( robot_task_interruptible = False
   →
   ( CRITICAL output is not suppressed ) )
```

*In every possible execution: the value of robot_task_interruptible has no
effect on whether CRITICAL is returned. It affects only how the integration
layer responds, not whether the safety signal is issued.*

---

### Proof Basis

These properties are proven by direct code inspection of `hsr/qerra_hsr.py`
and confirmed empirically by the 12-case regression suite in
`hsr/test_hsr_cases.py`. For deterministic systems with constant thresholds
and no probabilistic components, code inspection constitutes formal proof.

No model checker is required for a system of this deterministic simplicity.
The thresholds are named constants. The logic is a single if/else chain.
Every branch is covered by the test suite.

---

### Scope Boundary

These properties guarantee the **output** of the HSR module: `status = CRITICAL`
and the correct `vectors_activated` list. The physical robot response to CRITICAL
status — halt, alert, power-down — is the responsibility of the integration
layer (Behavior Tree, ROS 2 node) and is outside the scope of this module.

Full system-level safety guarantees require formal verification of both the
HSR module and the integration layer together.

---

## 9. Regression Test Coverage

The 12-case test suite in `hsr/test_hsr_cases.py` provides complete coverage
of all activation paths, boundary conditions, and architectural contracts.

| Test | Condition tested | Expected status |
|---|---|---|
| `test_clear_no_signals` | All signals at baseline | CLEAR |
| `test_clear_just_below_monitor_threshold` | confidence = 0.44 | CLEAR |
| `test_monitor_mild_distress_with_people_nearby` | confidence = 0.55, count = 3 | MONITOR |
| `test_monitor_at_exact_monitor_threshold` | confidence = 0.45 exactly | MONITOR |
| `test_critical_high_distress_alone` | confidence = 0.82, count = 4 | CRITICAL |
| `test_critical_at_exact_critical_threshold` | confidence = 0.75 exactly | CRITICAL |
| `test_critical_combined_distress_and_isolation` | confidence = 0.60, count = 0 | CRITICAL |
| `test_critical_environmental_hazard_only` | hazard = True, confidence = 0.10 | CRITICAL |
| `test_critical_all_vectors_active` | All three conditions met | CRITICAL |
| `test_interruptible_false_does_not_prevent_critical` | interruptible = False | CRITICAL |
| `test_result_always_has_reasoning` | All status levels | Non-empty reasoning string |
| `test_result_version_is_correct` | Any input | version = "0.1" |

All 12 tests must pass before any commit to main.

Run with:

```bash
python -m pytest hsr/test_hsr_cases.py -v
```

---

*QERRA-HSR v0.1 — deterministic physical safety companion to SEMEV-12*
*Part of QERRA-v2 Classical — ethical conscience as the foundation of every decision.*
