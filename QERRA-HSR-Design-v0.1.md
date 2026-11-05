# QERRA-HSR v0.1 — Design Document

**Status:** Hardened & Verified in simulation (v2.0.1) — September 2026; revised 5 November 2026  
**Original Release:** 12 June 2026  
**Author:** Marussa Metocharaki  
**Repository:** https://github.com/marunigno-ship-it/QERRA-v2-classical  
**Companion to:** SEMEV-12 v1.9.1 and Supervisory Gate Core v0.4

---

## 1. Purpose and Scope

QERRA-HSR is a deterministic physical-reflex companion layer designed for humanoid and collaborative mobile robots. It works alongside SEMEV-12 to handle immediate physical-reflex conditions, while SEMEV-12 evaluates high-level ethical deliberation. The HSR classifier is a local pure-Python computation; any sub-millisecond figure refers to the software evaluation path, not guaranteed end-to-end perception-to-actuation latency.

QERRA-HSR is also the reflexive companion of the Supervisory Gate (Layer 1A). The Gate consumes HSR state in the Webots controllers (in-process or asynchronous UDP) and in `qerra_gate_node` through `HsrReceiver`, using UDP port 5008 by default; the ROS 2 node exposes this as the `hsr_port` parameter. On a Gate evaluation tick that drains and accepts a valid `CRITICAL` HSR packet, Gate Core returns `TRIP_HSR_CRITICAL` with zero wheel commands, and the ROS 2 node publishes a zero `Twist` command during that tick. This describes the software decision/publication path; it is not a hard-real-time deadline or a physical stopping guarantee. In the API pipeline, a `CRITICAL` result also suspends SEMEV-12 evaluation immediately. See Section 10 for the telemetry contract, stream monitor and documented trust boundaries.

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
| `CRITICAL` | Immediate physical response required — motors commanded to 0.0, SEMEV-12 suspended |

---

## 5. Key Design Principles

- **Pure Python, zero ML:** Zero extra dependencies, runs on local CPU.
- **Same-tick reflex, measured in simulation:** The HSR evaluation is pure Python with a sub-millisecond software compute budget. In Webots, the commanded velocity is clamped to 0.0 rad/s on the same 32 ms tick as the injected `CRITICAL` input (cycle 125 in Demo 9). The full gate cycle in that run, which includes logging, averaged 1.38 ms (p99 3.70 ms, max 4.50 ms).

  Physical stopping distance depends on actuator dynamics: about 0.9 cm over about 0.08 s at 0.33 m/s was measured on a 56.58 kg four-wheeled test platform in Webots (not the TIAGo). This is a simulation measurement, not a hardware result.
- **Fully deterministic & explainable:** Auditable logic with human-readable reasoning traces.
- **Fail-closed precedence:** A `CRITICAL` output suspends SEMEV-12 deliberation immediately (API pipeline) and trips the Supervisory Gate to 0.0 rad/s (Webots controllers and `qerra_gate_node`).
- **The "HOW, never WHETHER" Contract:** Emergency halts are absolute ("never WHETHER"). Task interruptibility governs the **Recovery Directive** ("affects HOW") once safe conditions are restored.

---

## 6. Status

Hardened and exercised in simulation (Webots R2025a, PAL Robotics TIAGo AMR). The HSR package contains 20 tests: 14 core regression cases (`hsr/test_hsr_cases.py`) and 6 hysteresis stabilizer tests (`hsr/test_hysteresis.py`). These tests cover the listed HSR classification and recovery cases; they do not validate live perception or physical stopping behavior.

Related Gate/HSR test modules are present under `tests/`, including Gate/HSR state integration (`test_gate_hsr.py`), telemetry parsing and reduction (`test_gate_hsr_telemetry.py`), Gate clear-dwell behavior (`test_gate_hsr_clear_dwell.py`), an asynchronous UDP pipeline test (`test_async_hsr_pipeline.py`), synthetic telemetry scenarios (`test_synthetic_hsr_telemetry.py`), and adversarial UDP-ingestion demonstrations (`test_adversarial_hsr.py`). Their scopes are not interchangeable: for example, `test_async_hsr_pipeline.py` exercises the `drain_hsr_telemetry()` path, whereas the current node receiver uses `HsrReceiver` and `step_hsr_stream()`.

The project reports a 211-case host-test total. This is a project-reported inventory, not a claim that all 211 cases are independently verified or executed by one CI workflow. The currently inspected `.github/workflows/tests.yml` runs `tests/test_gate_*.py`, the `hsr/test_*.py` suite, the license-boundary test and the SEMEV-12 regression command. The `test_adversarial_hsr.py`, `test_async_hsr_pipeline.py` and `test_synthetic_hsr_telemetry.py` filenames do not match the `test_gate_*.py` discovery pattern; their execution by that workflow is therefore not established by that workflow file. Check the relevant workflow runs or add explicit test commands before describing these particular modules as CI-verified.

**Non-claims:** HSR inputs in the simulation demonstrations are injected or synthetic and have not been evaluated against a physical, live perception pipeline. The system has not been tested on physical hardware. QERRA-HSR is not a certified safety function and does not establish a physical stopping guarantee.

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

The following Linear Temporal Logic (LTL) expressions specify intended HSR properties. Deterministic implementation and code inspection help assess the underlying transition logic, but determinism alone does not constitute a formal proof of temporal properties. In particular, an eventuality (`◇`) requires explicit assumptions about input delivery and execution. The tests cited below provide finite regression evidence, not exhaustive formal verification.

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

### Evidence Basis and Verification Limit

The HSR properties are reflected in the implementation of `hsr/qerra_hsr.py` and exercised by the 14-case regression suite in `hsr/test_hsr_cases.py` and 6-case suite in `hsr/test_hysteresis.py`. These are code-inspection and finite-test evidence for the stated cases; they are not a machine-checked LTL proof. A formal verification claim would require a defined transition-system model, assumptions about inputs and timing, and an appropriate proof or model-checking result.

---

## 9. Regression Test Coverage

The 14-case test suite in `hsr/test_hsr_cases.py` covers the listed activation paths, threshold boundaries, and output contracts. The 6 hysteresis stabilizer tests in `hsr/test_hysteresis.py` bring the HSR package total to 20 tests.

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

All 14 tests must pass before any commit to `main`.

Run with:

```bash
python -m unittest hsr.test_hsr_cases -v
```

### Related Gate–HSR and telemetry tests

The repository also contains tests that exercise different parts of the wider integration:

- `tests/test_gate_hsr.py`: Gate Core behavior for HSR `CRITICAL`, required/missing HSR, stale HSR, reset interlocks and fail-closed outputs.
- `tests/test_gate_hsr_telemetry.py`: integer-permille classification, packet schema/timestamp checks and worst-severity reduction. This file does not, by itself, cover the full `step_hsr_stream()` rebase state machine.
- `tests/test_gate_hsr_clear_dwell.py`: Gate-level continuous-`CLEAR` dwell and operator-reset behavior when `hsr_required=True`.
- `tests/test_adversarial_hsr.py`: two adversarial demonstrations described in Section 10.
- `tests/test_async_hsr_pipeline.py` and `tests/test_synthetic_hsr_telemetry.py`: earlier synthetic asynchronous/Gate-input scenarios; these do not exercise every behavior of the current `HsrReceiver`/`step_hsr_stream()` path.

The current `tests.yml` workflow's `test_gate_*.py` selector includes files with that prefix, but does not select the three files whose names begin `test_adversarial`, `test_async` or `test_synthetic`. Confirm their execution separately before representing them as part of the automated CI result.

---

## 10. Integration with the Supervisory Gate — Telemetry Contract

The Supervisory Gate consumes validated HSR telemetry through `gate/hsr_telemetry.py` v0.3.1. In the ROS 2 node, `ros2/hsr_receiver.py` (`HsrReceiver`) receives UDP datagrams on localhost (`127.0.0.1`), default port 5008, configurable through the node's `hsr_port` parameter. The pure stream monitor `step_hsr_stream()` is actively called by `HsrReceiver.poll()` and its result is passed to `qerra_gate_node` and then to Gate Core.

| Item | Contract |
|---|---|
| Distress scale | Integer permille, 0 to 1000. Monitor threshold ≥ 450; critical threshold ≥ 750. This mirrors 0.45 and 0.75 without floating-point threshold comparisons in the wire classifier. |
| Classification | `CRITICAL` if distress ≥ 750, or hazard proximity is true, or distress ≥ 450 with persons nearby ≤ 1; `MONITOR` if distress ≥ 450 and no `CRITICAL` condition applies; otherwise `CLEAR`. If a `state` is declared in the packet, it must match the derived state. |
| Bounded ingestion | `HsrReceiver` drains at most `MAX_DRAIN_PER_CALL = 256` datagrams per `poll()` call. With the node's default `rate_hz = 31.25`, this is a maximum of 256 datagrams per nominal 32 ms Gate tick; the rate is configurable. |
| Packet fields | Required: `obs_id`, `t_obs_us`, `t_emit_us`, `distress_permille`. Optional: `hazard_proximity`, `persons_nearby_count`, `state`. Integer and Boolean fields are type-checked; the declared state is checked against the computed classification. |
| Timestamp checks | The parser checks `obs_id ≥ 0`, `t_obs_us ≥ 0`, `t_emit_us ≥ t_obs_us`, and `t_obs_us ≤ t_rx_us`. It rejects an observation timestamp later than Gate receipt time. The current parser does **not** check `t_emit_us ≤ t_rx_us`; therefore the full ordering `t_obs ≤ t_emit ≤ t_rx` is not enforced. The producer and Gate must use a compatible clock domain for the comparisons to be meaningful. |
| Arrival order and reduction | The stream monitor inspects every successfully parsed packet in socket-drain arrival order before reduction. In nominal operation, the batch reduction selects the worst severity (`CRITICAL` > `MONITOR` > `CLEAR`); ties are resolved by newest `t_obs_us`, then highest `obs_id`. |
| Regression handling | A repeated `obs_id` sets the sticky `frozen_latched` condition. A lower `obs_id` or a backward `t_obs_us` sets `rebase_in_progress`. During either condition the stream monitor returns `(None, None)`. This is a fail-closed stream state, not merely silent acceptance of the regressing packet. |
| Gate behavior | `CRITICAL` trips `TRIP_HSR_CRITICAL`. With `hsr_required=True`, missing/invalid stream output trips `TRIP_HSR_INVALID`, and an HSR observation older than `t_hsr_stale_us` (96 ms by the default profile) trips `TRIP_HSR_STALE`. With `hsr_required=False`, a missing `(None, None)` HSR output does not itself trip the Gate. |
| Diagnostics | `/gate/state` reports HSR status/source and receiver diagnostics, including `hsr_frozen`, `hsr_rebase_in_progress`, and `hsr_rebase_streak`. |

### Stream Freshness State Machine (`step_hsr_stream`)

1. **Per-packet inspection before reduction.** Each parsed packet is examined in arrival order across the drained batch. The monitor compares its `obs_id` and `t_obs_us` with the prior packet/accepted observation before the worst-severity reduction is applied.
2. **Sticky repeated-frame detection.** A repeated `obs_id` (equal to the current comparison counter, including a duplicate within a batch) sets `frozen_latched = True`. The stream output becomes `(None, None)` while the fault/recovery state is active.
3. **Controlled rebase.** A regressing `obs_id` or backward observation timestamp sets `rebase_in_progress = True` and clears the current recovery streak and start timestamp.
4. **Dual recovery criteria.** Rebase/freeze recovery requires both:
   - At least five qualifying packet-bearing polls/ticks, with a maximum of `+1` streak credit per poll even if multiple packets arrive in that poll; and
   - At least 160,000 µs of elapsed sensor-observation time, calculated as `t_obs_current - t_obs_start`.

   **Important implementation detail:** an idle poll with no successfully parsed packets does not earn streak credit, but it preserves the existing streak and dwell start timestamp. Therefore the current implementation requires five qualifying ticks plus the elapsed-time threshold; it does not strictly guarantee five uninterrupted/consecutive control ticks.
5. **Recovery-streak reset.** During recovery, a parsed `MONITOR` or `CRITICAL` packet, stale packet, repeated counter, or sequence/timestamp regression resets the streak and dwell start. A packet whose `t_obs_us` is later than Gate receipt time is rejected by `parse_hsr_telemetry()` before it reaches `step_hsr_stream()`. Malformed or oversized datagrams are also discarded before the stream monitor; if no successfully parsed packet remains in that poll, the idle-poll behavior described above applies (the existing streak and dwell start are preserved).
6. **Fail-closed output.** While `frozen_latched` or `rebase_in_progress` remains active, the stream monitor returns `(None, None)`. When `hsr_required=True`, Gate Core interprets the missing status as `TRIP_HSR_INVALID`. When `hsr_required=False`, missing HSR is an explicitly permitted legacy/optional mode and is not independently fail-closed by Gate Core.
7. **Diagnostic visibility.** The ROS 2 node includes `hsr_frozen`, `hsr_rebase_in_progress` and `hsr_rebase_streak` in `/gate/state` diagnostics.

### Documented Limits & Security Non-Claims

1. **Sequence-counter scope.** The stream monitor detects repeated/regressing counters and backward observation timestamps. It cannot determine whether a camera or perception pipeline is genuinely acquiring new sensor frames if a faulty or malicious publisher continues to generate fresh counters and timestamps while repeating stale perception content. No live perception freshness proof is provided.
2. **No producer identity or authentication.** The UDP receiver binds to localhost but does not authenticate the sender, verify a cryptographic message signature, or establish a producer session identity. Any local process able to send to the bound port may be able to inject syntactically valid telemetry. Localhost binding is not sender authentication.
3. **Optional HSR mode.** When `hsr_required=False`, a `(None, None)` output during a freeze/rebase or unavailable stream does not cause Gate Core to trip solely because HSR is absent. Fail-closed HSR enforcement therefore depends on `hsr_required=True`.
4. **Masked-distress re-arm demonstration.** `tests/test_adversarial_hsr.py::test_adversarial_masked_distress_rearm_succeeds_without_auth` demonstrates that, after a `CRITICAL` event and silence of the genuine producer, forged unauthenticated localhost HSR packets can satisfy the receiver's rebase recovery and subsequent Gate `CLEAR` dwell. The test then supplies `RESET_SOURCE_OPERATOR` directly through `GateInputs` and confirms that Gate Core returns to `RUN`. This is a synthetic cross-component vulnerability demonstration; the test does not itself demonstrate that the same UDP sender can publish an authorized ROS 2 `/gate/reset` message or compromise the ROS 2 reset interface.
5. **Ingestion crowding demonstration.** `tests/test_adversarial_hsr.py::test_adversarial_flood_above_max_drain_delays_critical` places 260 valid `CLEAR` datagrams ahead of a `CRITICAL` datagram. Because the receiver drains at most 256 datagrams in one poll, the first poll returns `CLEAR` and the `CRITICAL` packet is not processed until the next poll in the test. This is a receiver-level UDP ingestion denial-of-service demonstration, not a measured ROS 2 executor or physical actuation delay. It shows that a bounded drain protects per-tick work but can also defer a critical packet queued behind a sufficiently large burst.
6. **Timestamp trust and clock domain.** Timestamps are producer-supplied. The parser checks observation time against emission time and Gate receipt time, but does not authenticate those timestamps or require `t_emit_us ≤ t_rx_us`. The comparisons also assume a shared/compatible clock domain. A producer can lie consistently about its timestamps.
7. **No hard-real-time or physical guarantee.** UDP delivery, socket queueing, polling cadence, ROS 2 executor scheduling, command transport, base-controller response and actuator braking are outside the pure stream monitor's proof boundary. A same-tick software decision is not a guaranteed end-to-end response time or a physical emergency-stop function.

---

*QERRA-HSR v0.1 — deterministic physical safety companion to SEMEV-12*  
*Part of QERRA-v2 Classical — ethical conscience as the foundation of every decision.*
