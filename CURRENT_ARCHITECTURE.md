# CURRENT_ARCHITECTURE.md
# QERRA-v2 Classical — Architecture Documentation
# Version: 2.1.0 (Supervisory Gate v0.3 + QERRA-HSR v0.1 + SEMEV-12 v1.9.2 + QERRA-THRIVE v2.0.0)
# Last updated: October 2026

---

## 1. Overview

QERRA-v2 Classical is a deterministic, fully explainable, three-layer ethical and safety evaluation middleware engine for autonomous AI systems and robots (ROS 2 + PyTrees), combined with a supervisory execution gate that holds exclusive authority over a mobile base's wheel commands.

Design principle: **values and ethics can screen and rank what a robot wants to do, but only a deterministic gate decides what the wheels do.**

The architecture has two separate paths:

* **Actuation path (authoritative):** an untrusted proposer sends wheel-speed proposals to the Supervisory Gate (Layer 1A), which is the only component that writes wheel commands.
* **Deliberation path (advisory):** inside robot Behavior Trees and the HTTP API, QERRA evaluates the situation description and candidate choices (Layers 1B, 2 and 3) and returns auditable decisions and winning action selections with full score traces. Its primary purpose is to act as a **Condition gate** (Layers 1B & 2) and **Action Ranker selector** (Layer 3).

As of October 2026, QERRA-v2 Classical consists of:
1. **Layer 1A — Supervisory Gate v0.3 (`gate/`, AGPL-3.0-only):** Pure-function integer state machine with exclusive wheel-command authority, a kinematic stopping envelope, fail-closed latching and a tamper-evident decision log.
2. **Layer 1B — QERRA-HSR v0.1 (`hsr/`, Apache-2.0):** Pure-Python physical safety reflex (distress, isolation, hazard proximity) for the deliberation path.
3. **Layer 2 — SEMEV-12 v1.9.2 (AGPL-3.0):** Moral deliberation engine for harm/coercion screening of text instructions.
4. **Layer 3 — QERRA-THRIVE v2.0.0 (AGPL-3.0):** Advisory Action Ranker evaluating HRI and ecological values across candidate text choices.

### Evidence status by component

| Component | Status |
|-----------|--------|
| Layer 1A Supervisory Gate | Demonstrated in simulation only (Webots R2025a, PAL Robotics TIAGo base, Windows 11, non-real-time host). Single baseline run (n=1): Demo 7, `RUN_1791713619`. |
| Layer 1B QERRA-HSR | Implemented and unit-tested. Activation thresholds are design estimates, not empirically calibrated. |
| Layer 2 SEMEV-12 | Advisory; not part of the safety function. Benchmarked (80-case baseline, adversarial suite). The adversarial benchmark documents known bypasses and false positives. |
| Layer 3 QERRA-THRIVE | Advisory. Unit-tested. Not yet evaluated with human participants. |

### Integration status

The actuation path and the deliberation path are architecturally separate and are not connected by any code path today. Demo 7 drives the Supervisory Gate with a scripted untrusted proposer (`scripts/untrusted_proposer.py`); no demo connects the gate to SEMEV-12, THRIVE or the Behavior Tree nodes. As of v0.3 the gate does not import `hsr/`. Demos 1–6 predate the gate; only Demo 7 uses it.

---

## 2. System Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│        PLANNERS / LLMs / BEHAVIOR TREES  (untrusted proposers)             │
└───────────────┬─────────────────────────────────────────┬──────────────────┘
                │ candidate actions / text instructions   │ wheel-speed proposals
                ▼ DELIBERATION PATH (advisory)            ▼ ACTUATION PATH (UDP, authoritative)
   ┌─────────────────────────────┐             ┌─────────────────────────────┐
   │ Layer 1B  QERRA-HSR         │             │ Layer 1A  SUPERVISORY GATE  │
   │ Layer 2   SEMEV-12          │             │ gate/  (sole wheel owner)   │
   │ Layer 3   QERRA-THRIVE      │             │ + lidar, operator reset     │
   └─────────────────────────────┘             └──────────────┬──────────────┘
                                                              │ wheel commands
                                                              ▼
                                                       wheel motors
```

### Layer 1A: Supervisory Gate v0.3 (Actuator Authority)
* **Directory:** `gate/` (AGPL-3.0-only). Also: `verify_log.py`, `controllers/tiago_supervisory_gate/` (Webots controller), `worlds/demo7_supervisory_gate.wbt`, `scripts/untrusted_proposer.py`.
* **Modules:**
  - `gate_core.py` — pure function `step(state, params, inputs) -> StepResult`. Standard library only; no sockets, files, Webots, clock or randomness. Time arrives as `inputs.sim_time_us`. An AST unit test (`test_gate_core_imports_stdlib_only`) verifies it imports only standard-library modules and never `hsr`.
  - `gate_ipc.py` — non-blocking UDP receiver on localhost. Drain is bounded to 256 datagrams per call, messages are capped at 2048 bytes, strictly parsed (integers only, NaN/Infinity rejected).
  - `gate_lidar.py` — `CorridorFilter`: keeps lidar samples inside the robot's forward swept corridor and replaces other valid samples with `+inf`. Invalid values pass through unchanged so the gate trips on them.
  - `gate_link.py` — one-way gate → proposer channel that echoes simulation time, so proposal age is measured on the gate's clock.
  - `gate_log.py` — tamper-evident flight recorder.
* **Units:** integers everywhere that is logged — time in microseconds, wheel speed in micro-radians per second, distance in millimetres.
* **Parameters:** held in an immutable `GateParams` (validated on construction). No input can change them.
* **Authority rules:** the gate is the only process that writes wheel velocities. A proposal can only be clamped down into the gate envelope, never raised. Proposals must carry strictly increasing sequence numbers and cannot be stamped in the future.
* **Stopping envelope:** `d_stop(v) = ceil(v² / (2 · a_design)) + margin`, computed from the larger of the last commanded wheel speed and the newly proposed (clamped) wheel speed. An obstacle hazard is `min_range <= d_stop` (AR-9).
* **Modes:** `RUN`, `TRIPPED`, `AWAITING_RESET`. The gate starts `TRIPPED` (fail-closed). Any non-`RUN` mode commands zero on both wheels.
* **Trip reasons (fixed priority, one primary reason per tick):** `TRIP_LOG_FAILURE`, `TRIP_SENSOR_INVALID`, `TRIP_OBSTACLE`, `TRIP_PROPOSER_DEAD`, `TRIP_PROPOSER_STALE`; a non-increasing simulation clock trips as `TRIP_CLOCK_ANOMALY`. Latched states report `LATCHED_DWELL` and `LATCHED_AWAIT_RESET`; an accepted reset reports `RESET_ACCEPTED`.
* **Lidar validation:** the scan must have the exact expected sample count and be fresh. Any NaN, non-positive or non-numeric sample invalidates the scan and trips the gate. A scan of all `+inf` is treated as valid with no return (see Section 6).
* **Recovery contract:** after a trip, the gate stays latched until the hazard is clear for a continuous 1.0 s dwell and an explicit operator reset arrives. Only the exact source `operator` is accepted (keyboard `R`, edge-triggered, or the string `operator` on the operator UDP channel). Reset during a hazard is rejected (`RESET_REJECTED_HAZARD`). Proposer-channel resets are rejected (`RESET_REJECTED_CHANNEL`).
* **Default Demo 7 parameters:**

| Parameter | Value |
|-----------|-------|
| Control tick (`dt_us`) | 32,000 µs (Webots `basicTimeStep`) |
| Proposer freshness limit (`t_watch_us`) | 150,000 µs (150 ms) |
| Lidar freshness limit (`t_stale_us`) | 96,000 µs (3 × dt) |
| Continuous-clear dwell (`t_dwell_us`) | 1,000,000 µs (1.0 s) |
| Design deceleration (`a_design_mmps2`) | 500 mm/s² |
| Safety margin (`margin_mm`) | 300 mm |
| Wheel radius | 98 mm (TIAGo base) |
| Wheel speed envelope | 0 to 3,000,000 µrad/s (3.0 rad/s), capped by the motor maximum in the controller; no reverse |
| Lidar | Hokuyo, 667 samples, 240° field of view, 0.32 m half-width corridor (0.64 m) |

* **Flight recorder:** every evaluation appends one canonical JSON line (sorted keys, fixed separators, binary LF) to `results/<run_id>/gate_audit.jsonl`. Each record carries `prev_hash` and `hash = SHA256(prev_hash || canonical_bytes)`, starting from a genesis hash of 64 zeros. `verify_log.py` checks sequence continuity, strictly increasing simulation time, absence of CRLF corruption, the hash chain, and optionally an externally anchored head sequence number and hash. The chain is tamper-evident, not unforgeable. The anchor (`results/RUN_1791713619/ANCHOR.txt`) is stored in this same repository.
* **v0.3 change (decoupling):** the gate no longer imports `hsr/`. The previous call into `evaluate_hsr` (with fixed distress and person-count values) was replaced by the direct check above. The step record carries `obstacle_breach`; the `hsr_status` log field is written as `null` and is reserved for external assistive-reflex telemetry. See Section 6 for the current state of the `obstacle_breach` field in the written log.

### Layer 1B: QERRA-HSR v0.1 (Physical Safety Guard)
* **Directory:** `hsr/` (Apache-2.0, with `hsr/LICENSE` and `hsr/NOTICE`).
* **Properties:** Pure Python standard library, zero ML, threshold logic. Invalid, missing or out-of-range telemetry (None, NaN, Inf, wrong types, negative counts) fails closed to `CRITICAL`.
* **Vectors (3):** `immediate_physical_distress`, `human_isolation`, `environmental_hazard_proximity`.
* **Thresholds (design estimates):** distress confidence ≥ 0.75 gives `CRITICAL`, ≥ 0.45 gives `MONITOR`; person isolation means a nearby-person count ≤ 1 and only activates together with a distress signal.
* **Output:** `CLEAR`, `MONITOR`, or `CRITICAL`, plus reasoning and a `recovery_directive`. If `CRITICAL`, higher-level deliberation is suspended immediately. `robot_task_interruptible` affects how recovery is handled, never whether a hazard is acted on: for a non-interruptible task the directive after `CLEAR` is to hold for a person to confirm before continuing.
* **Stabilizer:** `hsr/hysteresis_wrapper.py` (`StabilizedHSR`) holds an elevated status until a calmer reading has persisted for a 1.0 s dwell, preventing sensor flutter from causing premature de-escalation.

### Layer 2: SEMEV-12 v1.9.2 (Moral Deliberation Engine)
* **Files:** `ethical_core.py`, `vectors.py`
* **Properties:** Multi-anchor max-pooling (`all-MiniLM-L6-v2`) combined with deterministic regex mechanisms: pattern fallbacks, a v005 direct-negation pre-filter (`_v005_negation_guard`), hardened safety-override paraphrase patterns, and an absolute severe-harm veto.
* **Vectors (12):** `v001` through `v012` (coherence protection, family severance, survival instinct, moral pressure, harm intent, family origin chain, personal potential, shallow remorse, ethical severance, cognitive manipulation, autonomy violation, institutional trust).
* **Output:** `decision: safe` (score ≤ 0.5) or `decision: modified` (score > 0.5). A `modified` decision blocks the Behavior Tree condition. Advisory with respect to wheel authority: SEMEV-12 is not part of the safety function.

### Layer 3: QERRA-THRIVE v2.0.0 (Values Companion Layer & Action Ranker)
* **Directory:** `values/`
* **Properties:** Non-blocking advisory Action Ranker evaluating candidate response text options in Behavior Trees. Bounded look-back negation guards are used across the vectors.
* **Sub-Package Structure:**
  - `values/human_centered/` (Suite A — 9 Human-Centered Vectors)
  - `values/ecological/` (Suite B — 3 Ecological & Sustainable Vectors)
* **Total THRIVE Vectors (12):**
  1. `transparent_disclosure` (hybrid)
  2. `balanced_pacing` (hybrid)
  3. `stated_preference_respect` (hybrid)
  4. `sovereign_independence` (hybrid)
  5. `constructive_empathy` (hybrid)
  6. `unbiased_perception` (hybrid)
  7. `spatial_discretion` (hybrid)
  8. `observational_consent` (hybrid)
  9. `proactive_clarity` (dual-regex hybrid)
  10. `flora_boundary_protection` (hybrid + gardening exception)
  11. `animal_startle_avoidance` (hybrid + negation guard + pet-care exception)
  12. `minimal_disturbance_footprint` (hybrid + negation guard + emergency boost)

### Timing and Watchdog Budgets

The two paths use different, unrelated budgets:

| Budget | Value | Where | Purpose |
|--------|-------|-------|---------|
| Gate control tick | 32 ms | Webots controller | One gate evaluation per tick |
| Proposer freshness | 150 ms | `gate_core.py` (`t_watch_us`) | Stale or absent proposals trip the gate |
| Lidar freshness | 96 ms | `gate_core.py` (`t_stale_us`) | Stale scans trip the gate |
| Clear dwell before reset | 1.0 s | `gate_core.py` (`t_dwell_us`) | Continuous clear time before an operator reset can be accepted |
| HSR stabilizer dwell | 1.0 s | `hsr/hysteresis_wrapper.py` | Holds an elevated HSR status until calm readings persist |
| Remote API timeout | 800 ms | `ros2_bridge.py` (`API_TIMEOUT_SECONDS`) | Remote SEMEV-12 call; on timeout or network error the bridge falls back to the local model |

The 800 ms figure is a remote-call timeout on the deliberation path. It is not a wheel-level watchdog.

---

## 3. Behavior Tree Integration & Nodes

QERRA-v2 Classical provides two dedicated PyTrees Behavior nodes:

1. **`QerraConditionNode` (`qerra_condition_node.py` / `qerra_standalone_remote_node.py`):**  
   Non-blocking Condition node evaluating Layer 1B (QERRA-HSR) and Layer 2 (SEMEV-12). It returns `RUNNING` while the evaluation is pending, `SUCCESS` only when the goal is accepted, the result succeeds and the decision is `safe`, and `FAILURE` otherwise. Missing or malformed HSR telemetry is forwarded as invalid values so the bridge fails closed.
2. **`QerraActionRankerNode` (`qerra_action_ranker_node.py`):**  
   Non-blocking Action Ranker leaf node evaluating Layer 3 (QERRA-THRIVE) candidate action choices. Uses decision-point caching (`_dirty = True`) to execute sentence-transformer encodings (~25ms CPU) only when candidates change, preserving sub-millisecond tick speeds during routine ticks.

**ROS 2 bridge (`ros2_bridge.py`):**
* Standalone mode (no ROS 2) runs a direct local evaluation. With `rclpy` and `qerra_msgs` present it becomes an Action Server on `/qerra/evaluate` (`qerra_msgs/action/QerraEvaluate`), running on a `MultiThreadedExecutor` with a `ReentrantCallbackGroup`.
* Layer 1B is evaluated locally, with `StabilizedHSR` thread-safe wrapping. Missing, `None` or malformed telemetry returns a fail-closed critical result.
* Layer 2 is a hybrid: remote API first with the 800 ms timeout, then a locally pre-loaded SEMEV-12 model as fallback.

---

## 4. Interaction Between Layers

### Actuation path
* The Supervisory Gate is the only component that writes wheel commands. Proposers are untrusted: they can be late, wrong or dead, and the default is stop.
* The gate overrides the proposer on any trip and can only clamp proposals down, never raise them.
* The deliberation layers (1B, 2, 3) do not command wheels through the gate today (see Integration status in Section 1).

### Deliberation path

The execution sequence before a robot commits to an action:

```
[1. Layer 1B QERRA-HSR (Reflexive Safety)] ──► [2. Layer 2 SEMEV-12 (Moral Gate)] ──► [3. Layer 3 THRIVE (Action Ranker)] ──► [Selected action]
Local physical check                           Filters coercive/harmful candidates      Ranks only surviving safe candidates       Winning safe action
```

**Core Interaction Rules:**
* QERRA-HSR `CRITICAL` suspends SEMEV-12 deliberation and Layer 3 action ranking immediately.
* A SEMEV-12 `modified` decision is never overridden by Layer 3 advisory rankings.
* The three deliberation layers run in strict sequence (1B → 2 → 3); each layer only narrows what the next layer sees.
* Human physical or medical emergencies outrank Layer 3 advisory spatial or ecological courtesy via an explicit `EMERGENCY_BOOST = 0.35`.

---

## 5. Repository Package Structure

Key files and directories:

```
QERRA-v2-classical/
├── gate/                                # Layer 1A: Supervisory Gate v0.3 (AGPL-3.0-only)
│   ├── gate_core.py                     #   pure-function state machine (stdlib only)
│   ├── gate_ipc.py                      #   non-blocking UDP receiver
│   ├── gate_lidar.py                    #   swept-corridor lidar filter
│   ├── gate_link.py                     #   gate -> proposer sim-time channel
│   └── gate_log.py                      #   SHA-256 hash-chained flight recorder
├── verify_log.py                        # offline flight-recorder verifier
├── controllers/tiago_supervisory_gate/  # Webots controller for Demo 7
├── worlds/demo7_supervisory_gate.wbt    # Webots world for Demo 7
├── scripts/untrusted_proposer.py        # scripted untrusted proposer for Demo 7
├── results/RUN_1791713619/              # Demo 7 audit log, wheel telemetry, ANCHOR.txt
├── hsr/                                 # Layer 1B: QERRA-HSR (Apache-2.0)
│   ├── qerra_hsr.py
│   └── hysteresis_wrapper.py
├── values/                              # Layer 3 THRIVE package
│   ├── __init__.py                      #   top-level aggregator (ALL_THRIVE_VECTORS)
│   ├── thrive_vectors.py                #   backward-compatibility bridge
│   ├── human_centered/                  #   Suite A (Vectors 1–9)
│   │   ├── __init__.py
│   │   └── human_vectors.py
│   └── ecological/                      #   Suite B (Vectors 10–12)
│       ├── __init__.py
│       ├── ecological_vectors.py
│       ├── vector_flora_boundary_protection_spec.md
│       ├── vector_animal_startle_avoidance_spec.md
│       └── vector_minimal_disturbance_footprint_spec.md
├── ethical_core.py                      # Layer 2 SEMEV-12 engine (v1.9.2)
├── vectors.py                           # SEMEV-12 vector definitions
├── app.py                               # FastAPI reference application
├── qerra_condition_node.py              # Layer 1B/2 PyTrees Condition node
├── qerra_action_ranker_node.py          # Layer 3 PyTrees Action Ranker node
├── qerra_standalone_remote_node.py      # Condition node calling the live API over HTTP
├── demo_thrive_bt.py                    # Master 12-vector PyTrees BT demo
├── ros2_bridge.py                       # ROS 2 Action Server bridge
├── tests/                               # Regression, gate, license-boundary tests
├── .github/workflows/tests.yml          # CI workflow
├── setup.py / package.xml               # Packaging (qerra_core v2.1.0)
├── SAFETY_CONCEPT.md                    # Supervisory Gate safety concept (v0.3)
├── LIMITATIONS.md                       # Known limitations
└── CHANGELOG.md                         # Version history
```

### Licensing map

| Component | License |
|-----------|---------|
| `hsr/` (Layer 1B) | Apache-2.0 |
| `gate/`, `verify_log.py` (Layer 1A) | AGPL-3.0-only |
| SEMEV-12, QERRA-THRIVE (Layers 2 and 3) | AGPL-3.0 |

`tests/test_license_boundary.py` fails if any file in `hsr/` imports anything other than the Python standard library or `hsr` itself, lacks the Apache-2.0 SPDX header, or if `hsr/LICENSE` or `hsr/NOTICE` is missing.

### Packaging

`setup.py` and `package.xml` register `qerra_core` at v2.1.0 with license `AGPL-3.0-only AND Apache-2.0`. Packages: `gate`, `hsr`, `values`, `values.human_centered`, `values.ecological`, `auth`, `models`, `utils`. Modules include `verify_log`, `ros2_bridge`, `ethical_core`, `vectors`, `classical_analyze`, and the three node modules. Console entry point: `bridge = ros2_bridge:main`.

### Continuous Integration

The GitHub Actions workflow (`ubuntu-latest`, Python 3.10) runs 110 tests:
* Supervisory Gate: 75 tests (`tests/test_gate_*.py`: core, IPC, lidar, link, log), standard library only.
* QERRA-HSR: 20 tests.
* SEMEV-12: 15 golden regression cases (`tests/test_cases.py`).

`tests/test_license_boundary.py` (4 tests) is not part of the CI workflow and is run locally. The bridge fail-closed test (`tests/test_bridge_fail_closed.py`) and `test_pipeline_integration.py` are present in the repository but are also not part of the current CI workflow.

---

## 6. Current Limitations

**Layers 1B, 2 and 3**
- Layer 3 Action Ranking evaluates candidate text descriptions generated by a motion planner; it does not replace low-level motor controllers or physical perception stacks.
- Semantic thresholds and hybrid regex penalties calibrated on 12 representative scenario test suites. Open-domain generalization to significantly different candidate phrasings is bounded by transformer embedding norms.
- Local CPU model fallback (~250MB RAM) requires sentence-transformers and PyTorch/Torch.
- ROS 2 integration validated in WSL 2 / ROS 2 Humble simulation (PAL Robotics TIAGo in Webots R2025a).
- QERRA-HSR activation thresholds are design estimates and have not been calibrated against physical sensor streams.

**Layer 1A Supervisory Gate** (full detail in `LIMITATIONS.md` Section 3 and `SAFETY_CONCEPT.md`)
- **Simulation-only, n=1, non-real-time host:** The empirical baseline is a single run (`RUN_1791713619`, 1,485 control cycles, 47.52 s simulation time) on Windows 11, which is not a real-time OS. The 150 ms proposer freshness limit was set to tolerate host thread jitter.
- **Evidence predates v0.3:** `RUN_1791713619` was recorded with gate v0.2 (`ANCHOR.txt` reports `GATE_VERSION: 0.2`, and the logged records carry `hsr_status`). No Webots run with v0.3 is recorded in `results/`.
- **Commanded, not measured, velocity:** `d_stop` uses the commanded wheel speeds. In the Demo 7 telemetry, measured wheel rotation and commanded speed disagreed between t = 5.76 s and t = 14.40 s (consistent with caster drag or slip, an attribution not isolated by a separate experiment).
- **No reaction-time term:** `d_stop` has no explicit latency term; at the 0.196 m/s Demo 7 cruise speed the 300 mm margin absorbs it. `SAFETY_CONCEPT.md` requires adding one before operating at higher speeds.
- **Rotational sweep is unmodeled:** The corridor filter models forward translation only. A pivot-in-place command with an obstacle beside the chassis can evaluate as clear.
- **Blinded sensor boundary:** A scan of all `+inf` is treated as an unobstructed field, not as a sensor fault.
- **Strict invalid-data policy:** Any single invalid sample in a scan (NaN, non-positive, non-numeric) trips the gate. The policy has not been exercised with real lidar drivers.
- **Process-level separation only:** The gate and the proposer are separate OS processes on one non-real-time host, communicating over unauthenticated localhost UDP. This does not protect against gate process death or against malicious local processes (including a forged operator reset).
- **Flight recorder:** The log records gate commands, not wheel ground truth. The hash chain is tamper-evident against an anchored head hash only, and the anchor is stored in this repository.
- **`obstacle_breach` is not yet persisted:** `gate_core.step()` returns `obstacle_breach` in its step record, but `gate_log.py` builds the written record from a fixed field list that does not include it, so written logs contain `hsr_status: null` and no `obstacle_breach` field. `SAFETY_CONCEPT.md` v0.3 and `CHANGELOG.md` describe the field as part of the log schema. Update this section once `gate_log.py` writes it.

**Regulatory boundary**
QERRA-v2 Classical operates strictly as an unrated supervisory execution guard in high-level software. It is not a certified safety component under EU Machinery Regulation (EU) 2023/1230, provides no ISO 13849-1 Performance Level or IEC 62061 / IEC 61508 Safety Integrity Level rating, and any physical deployment must operate upstream of, and subordinated to, independent certified hardware emergency stops, certified safety laser scanners and Safe Torque Off (STO) relays.

---

## 7. Architecture Decision Records and Design Documents

| ADR            | Title                                              | Status   |
|----------------|----------------------------------------------------|----------|
| ADR-001        | Creation and Design of SEMEV-12 Ethical Framework  | Accepted |
| HSR-ADR-001    | Three-Vector Design Decision for QERRA-HSR v0.1    | Accepted |

There is no ADR for the Supervisory Gate. Its design record is `SAFETY_CONCEPT.md` (v0.3: claims and non-claims, hazards, parameters, architecture rules AR-1 to AR-9, audit-log schema).

---

*This document reflects the architecture as of v2.1.0 (October 2026).*
