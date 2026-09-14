# QERRA-HSR v0.1 — Design Document

**Status:** Hardened & Verified (v2.0.1) — September 2026  
**Original Release:** 12 June 2026  
**Author:** Marussa Metocharaki  
**Repository:** https://github.com/marunigno-ship-it/QERRA-v2-classical  
**Companion to:** SEMEV-12 v1.9.1  

---

## 1. Purpose and Scope

QERRA-HSR is a deterministic physical safety companion layer for humanoid and collaborative mobile robots. It works alongside SEMEV-12 to handle immediate physical safety reflexes with sub-millisecond latency, while SEMEV-12 evaluates high-level moral deliberation.

---

## 2. The Three Vectors

- **immediate_physical_distress (HSR-V01)**  
  Detects acute physical distress in nearby humans (screams, falls, severe injury).

- **human_isolation (HSR-V02)**  
  Detects when a distressed human is isolated (no other responsive humans nearby).

- **environmental_hazard_proximity (HSR-V03)**  
  Detects when a human or robot is in immediate proximity to a physical hazard.

---

## 3. Input Interface

```python
HSRInput(
    distress_confidence: float,        # 0.0–1.0 from perception stack
    persons_nearby_count: int,         # responsive bystanders nearby
    hazard_proximity_flag: bool,       # physical hazard proximity
    robot_task_interruptible: bool     # affects HOW, never WHETHER
)
```

---

### Note for integrators: computing `hazard_proximity_flag`

QERRA-HSR receives `hazard_proximity_flag` as a plain true/false signal — it does not calculate proximity itself. For anyone computing this flag from a real distance sensor: raw distance alone is a weak signal, since a robot approaching fast and one drifting slowly can be the same distance away with very different real risk. A stronger approach is time-to-collision (distance divided by closing speed), combined with a fixed minimum-distance floor for the case where the robot isn't moving at all (distance alone, closing speed near zero, should still trigger if the robot is simply too close).

---

## 4. Output Structure & States

```python
@dataclass
class HSRResult:
    status: HSRStatus
    vectors_activated: list[str]
    reasoning: str
    recovery_directive: str
    version: str = "0.1"
```

| State | Meaning |
|---|---|
| `CLEAR` | No safety signals detected — nominal operation |
| `MONITOR` | Elevated signal — proceed with caution, do not halt |
| `CRITICAL` | Immediate physical response required — motors clamped to 0.0, SEMEV-12 suspended |

---

## 5. Key Design Principles

- **Pure Python, zero ML:** Zero extra dependencies, runs on local CPU.
- **Sub-millisecond reflex:** Independently verified at **0.0 ms command delay** (<1 cm physical stopping distance at 0.33 m/s in simulation).
- **Fully deterministic & explainable:** Auditable logic with human-readable reasoning traces.
- **Fail-closed precedence:** A `CRITICAL` output suspends SEMEV-12 deliberation immediately.
- **The "HOW, never WHETHER" Contract:** Emergency halts are absolute ("never WHETHER"). Task interruptibility governs the **Recovery Directive** ("affects HOW") once safe conditions are restored.

---

## 6. Status

Hardened and verified in simulation (Webots R2025a, PAL Robotics TIAGo AMR). Fully covered by 14 core regression cases and 6 hysteresis stabilizer tests (20 tests passing).

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

### Recovery Directive Logic:

```
if status == CLEAR:
    if robot_task_interruptible:
        recovery_directive = "Clear now — resume as normal."
    else:
        recovery_directive = "Clear now, but this was interrupted mid-task — hold for a person to confirm before continuing."
else:
    recovery_directive = ""  # Silenced during active incidents
```

### Threshold Constants

All thresholds are named constants exposed for auditability and testing:

```python
DISTRESS_CRITICAL_THRESHOLD = 0.75
DISTRESS_MONITOR_THRESHOLD  = 0.45
ISOLATION_COUNT_THRESHOLD   = 1
```

---

## 8. Formal Safety Properties (LTL)

Because QERRA-HSR is purely deterministic — no ML, no probability, constant thresholds, pure Python if/else — its safety properties are provable by direct code inspection. 

**Notation:** □ means "Globally/Always" — ◇ means "Eventually"

---

**Property HSR-1a: High distress confidence triggers CRITICAL**
```
□( distress_confidence ≥ 0.75
   →
   ◇( status = CRITICAL ∧ immediate_physical_distress ∈ vectors_activated ) )
```

---

**Property HSR-1b: Combined moderate distress and isolation triggers CRITICAL**
```
□( ( distress_confidence ≥ 0.45 ∧ persons_nearby_count ≤ 1 )
   →
   ◇( status = CRITICAL ∧ immediate_physical_distress ∈ vectors_activated ) )
```

---

**Property HSR-2: Isolated distressed person activates human_isolation**
```
□( ( distress_confidence ≥ 0.45 ∧ persons_nearby_count ≤ 1 )
   →
   ◇( human_isolation ∈ vectors_activated ) )
```

---

**Property HSR-3: Environmental hazard triggers CRITICAL**
```
□( hazard_proximity_flag = True
   →
   ◇( status = CRITICAL ∧ environmental_hazard_proximity ∈ vectors_activated ) )
```

---

**Property HSR-4: Task interruptibility never suppresses CRITICAL**
```
□( robot_task_interruptible = False
   →
   ( CRITICAL output is not suppressed ) )
```

---

**Property HSR-5: Recovery directive governs safe resumption contract**
```
□( status = CLEAR ∧ robot_task_interruptible = True
   → recovery_directive = "Clear now — resume as normal." )

□( status = CLEAR ∧ robot_task_interruptible = False
   → recovery_directive = "Clear now, but this was interrupted mid-task — hold for a person to confirm before continuing." )

□( status ≠ CLEAR
   → recovery_directive = "" )
```

---

### Proof Basis

These properties are proven by direct code inspection of `hsr/qerra_hsr.py` and confirmed empirically by the 14-case regression suite in `hsr/test_hsr_cases.py` and 6-case suite in `hsr/test_hysteresis.py`.

---

## 9. Regression Test Coverage

The 14-case test suite in `hsr/test_hsr_cases.py` provides complete coverage of all activation paths, boundary conditions, and architectural contracts.

| Test | Condition tested | Expected output |
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
| `test_interruptible_false_does_not_prevent_critical` | interruptible = False | CRITICAL (never WHETHER) |
| `test_interruptible_affects_recovery_directive_when_clear` | interruptible True vs. False | Directives differ (affects HOW) |
| `test_recovery_directive_empty_during_active_incident` | status != CLEAR | directive == "" |
| `test_result_always_has_reasoning` | All status levels | Non-empty reasoning string |
| `test_result_version_is_correct` | Any input | version = "0.1" |

All 14 tests must pass before any commit to main.

Run with:
```bash
python -m unittest hsr.test_hsr_cases -v
```

---

*QERRA-HSR v0.1 — deterministic physical safety companion to SEMEV-12*  
*Part of QERRA-v2 Classical — ethical conscience as the foundation of every decision.*
