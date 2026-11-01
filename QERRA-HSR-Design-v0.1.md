# QERRA-HSR v0.1 — Design Document

**Status:** Hardened & Verified in simulation (v2.0.1) — September 2026; revised 1 November 2026  
**Original Release:** 12 June 2026  
**Author:** Marussa Metocharaki  
**Repository:** https://github.com/marunigno-ship-it/QERRA-v2-classical  
**Companion to:** SEMEV-12 v1.9.1  

---

## 1. Purpose and Scope

QERRA-HSR is a deterministic physical safety companion layer for humanoid and collaborative mobile robots. It works alongside SEMEV-12 to handle immediate physical safety reflexes with sub-millisecond latency, while SEMEV-12 evaluates high-level moral deliberation.

QERRA-HSR is also the reflexive companion of the Supervisory Gate (Layer 1A). The Gate consumes the HSR state directly, both in the Webots controllers (in-process, or asynchronous UDP) and in `qerra_gate_node` (UDP port 5008). A `CRITICAL` state trips the Gate to 0.0 rad/s on the same tick, regardless of any deliberation. In the API pipeline, a `CRITICAL` result also suspends SEMEV-12 evaluation immediately. See Section 10 for the telemetry contract.

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

**Perception boundary (non-claim).** QERRA-HSR consumes `distress_confidence`, `persons_nearby_count` and `hazard_proximity_flag` as given. In all simulation demonstrations these inputs are injected or synthetic. They have not been evaluated against a physical, live vision perception pipeline. The activation thresholds are design estimates and have not been calibrated against sensor streams.

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
- **Same-tick reflex, measured in simulation:** The HSR evaluation is pure Python with a sub-millisecond software compute budget. In Webots, the commanded velocity is clamped to 0.0 rad/s on the same 32 ms tick as the injected `CRITICAL` input (cycle 125 in Demo 9). The full gate cycle in that run, which includes logging, averaged 1.38 ms (p99 3.70 ms, max 4.50 ms). Physical stopping distance depends on actuator dynamics: about 0.9 cm over about 0.08 s at 0.33 m/s was measured on a 56.58 kg four-wheeled test platform in Webots (not the TIAGo). This is a simulation measurement, not a hardware result.
- **Fully deterministic & explainable:** Auditable logic with human-readable reasoning traces.
- **Fail-closed precedence:** A `CRITICAL` output suspends SEMEV-12 deliberation immediately (API pipeline) and trips the Supervisory Gate to 0.0 rad/s (Webots controllers and `qerra_gate_node`).
- **The "HOW, never WHETHER" Contract:** Emergency halts are absolute ("never WHETHER"). Task interruptibility governs the **Recovery Directive** ("affects HOW") once safe conditions are restored.

---

## 6. Status

Hardened and verified in simulation (Webots R2025a, PAL Robotics TIAGo AMR). Fully covered by 20 tests in `hsr/`: 14 core regression cases (`hsr/test_hsr_cases.py`) and 6 hysteresis stabilizer tests (`hsr/test_hysteresis.py`).

Non-claims: distress inputs in the simulation demonstrations are injected or synthetic and have not been evaluated against a physical, live vision perception pipeline. Nothing here has been tested on hardware, and QERRA-HSR is not a certified safety function.

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

The 14-case test suite in `hsr/test_hsr_cases.py` provides complete coverage of all activation paths, boundary conditions, and architectural contracts. The 6 hysteresis stabilizer tests in `hsr/test_hysteresis.py` bring the total in `hsr/` to 20 tests.

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

## 10. Integration with the Supervisory Gate (Telemetry Contract)

The Supervisory Gate consumes the HSR state as a validated telemetry packet (`gate/hsr_telemetry.py`, v0.2.0), in the Webots controllers (in-process or UDP) and in `qerra_gate_node` (UDP port 5008, localhost only).

| Item | Contract |
|---|---|
| Distress scale | Integer permille, $0$ to $1000$ (no floating point at the thresholds). Monitor threshold $\ge 450$, critical threshold $\ge 750$, mirroring $0.45$ and $0.75$. |
| Classification | Identical to Section 7: `CRITICAL` if distress $\ge 750$, or hazard proximity, or distress $\ge 450$ with persons nearby $\le 1$; `MONITOR` if distress $\ge 450$; otherwise `CLEAR`. A declared `state` that disagrees with the derived state is rejected. |
| Packet fields | `obs_id` (monotonic frame counter), `t_obs_us`, `t_emit_us`, `distress_permille`, optional `hazard_proximity`, `persons_nearby_count`, optional `state`. All numeric fields are strict integers. |
| Causality | $0 \le t_{obs} \le t_{emit}$, and $t_{obs} \le t_{rx}$ (the Gate's receipt time). A future-stamped or causally inverted packet is dropped. |
| Reduction | All valid packets drained in one tick are reduced to the worst severity; ties go to the freshest observation. |
| Gate behaviour | `CRITICAL` trips `TRIP_HSR_CRITICAL`. With `hsr_required=True`, missing telemetry trips `TRIP_HSR_INVALID` and a heartbeat older than $96\text{ ms}$ trips `TRIP_HSR_STALE`. Recovery needs the Gate's own continuous `CLEAR` dwell (see `SAFETY_CONCEPT.md`, C-7b). |

Limits of this contract: the UDP channel has no sender authentication, and `is_perception_frozen()` (frame-counter regression check) exists in `gate/hsr_telemetry.py` but is not called at runtime by `qerra_gate_node`, so only heartbeat staleness is enforced there. The perception boundary in Section 3 applies.

---

*QERRA-HSR v0.1 — deterministic physical safety companion to SEMEV-12*  
*Part of QERRA-v2 Classical — ethical conscience as the foundation of every decision.*
