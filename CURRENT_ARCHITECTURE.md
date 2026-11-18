# CURRENT_ARCHITECTURE.md
# QERRA-v2 Classical — Architecture Documentation
# Version: 2.4.1 (Supervisory Gate Core v0.4 + HSR Telemetry Contract v0.4.0 + ROS 2 Jazzy Node v0.3.1 + QERRA-HSR v0.1 + SEMEV-12 v1.9.2 + QERRA-THRIVE v2.0.0)
# Last updated: November 2026

---

## 1. Overview

QERRA-v2 Classical is a deterministic, explainable, three-layer ethical and safety evaluation middleware engine for autonomous AI systems and robots (ROS 2 + PyTrees), combined with a supervisory execution gate that holds designated software authority over a mobile base's wheel commands.

Design principle: **values and ethics can screen and rank what a robot wants to do, but only a deterministic gate decides what the wheels do.**

The architecture has two separate paths:

* **Actuation path (authoritative):** an untrusted proposer sends wheel-speed proposals to the Layer 1A Supervisory Gate. The Gate Core evaluates proposals against the kinematic stopping envelope, lidar integrity and freshness, command freshness, clock behaviour and Layer 1B HSR telemetry. In the Webots controller, the Gate is the only process that writes simulated wheel velocities. In ROS 2, `qerra_gate_node` publishes the designated base-controller command topic; ROS 2 topics do not enforce a sole publisher, so the integrator must configure the base controller to accept commands only from that path.
* **Deliberation path (advisory):** the HTTP API, PyTrees nodes and `ros2_bridge.py` evaluate situation descriptions and candidate choices. SEMEV-12 screens text instructions and QERRA-THRIVE ranks candidate action descriptions. These layers return auditable decisions and score traces; they are not connected to wheel authority today.

As of November 2026, QERRA-v2 Classical consists of:
1. **Layer 1A — Supervisory Gate Core v0.4 (`gate/`) + ROS 2 node (`ros2/qerra_gate_node.py`) v0.3.1 (Apache-2.0):** Pure-function integer state machine with a dynamic stopping envelope, fail-closed latching, command-proposal inhibition, and a tamper-evident decision log. The ROS 2 adapter connects the core to `/cmd_vel`, `/scan`, reset and HSR telemetry interfaces.
2. **Layer 1B — QERRA-HSR v0.1 (`hsr/`, Apache-2.0):** Pure-Python physical/social reflex classifier (distress, isolation, hazard proximity). It supplies reflex status to both the API deliberation path and, through the v0.4.0 wire contract and `HsrReceiver`, the Gate actuation path.
3. **Layer 2 — SEMEV-12 v1.9.2 (Apache-2.0):** Advisory moral deliberation engine for harm/coercion screening of text instructions.
4. **Layer 3 — QERRA-THRIVE v2.0.0 (Apache-2.0):** Advisory Action Ranker evaluating HRI and ecological values across candidate text choices.

### Evidence status by component

| Component | Status |
|-----------|--------|
| Layer 1A Supervisory Gate | Demonstrated in Webots R2025a (Demos 7, 8 and 9 — PAL Robotics TIAGo base, Windows 11 non-real-time host) and built/exercised in native **ROS 2 Jazzy** container CI (43 integration tests across 6 modules). Not yet tested on physical hardware. |
| Layer 1B QERRA-HSR | Implemented and unit-tested (20 tests in `hsr/`, plus a 28,028-case conformance sweep in `tests/test_hsr_conformance.py`). The HSR-to-Gate actuation relationship is demonstrated in Webots Demo 9; the ROS 2 implementation uses `gate/hsr_telemetry.py` v0.4.0 and `ros2/hsr_receiver.py`, and is exercised in native ROS 2 Jazzy CI. Activation thresholds (0.45 / 0.75) are author-chosen ODD placeholders, not validated biometrics or validated perception outputs. |
| Layer 2 SEMEV-12 | Advisory; not part of the safety function. Benchmarked (80-case baseline, adversarial suite). The adversarial benchmark documents known bypasses and false positives. |
| Layer 3 QERRA-THRIVE | Advisory. Unit-tested. Not yet evaluated with human participants. |

### Integration status

The actuation path integrates Layer 1A (`gate_core.py` v0.4) with Layer 1B HSR reflex status. Webots Demo 9 demonstrates an HSR-triggered Gate trip; the ROS 2 implementation receives HSR telemetry over UDP port 5008 through `gate/hsr_telemetry.py` v0.4.0 and `HsrReceiver` in `qerra_gate_node`. A valid HSR `CRITICAL` status can trip the Gate. Layers 2 (`SEMEV-12`) and 3 (`QERRA-THRIVE`) remain on the separate advisory deliberation path (`ros2_bridge.py`, HTTP API and PyTrees) and are not connected to wheel authority today. The architecture therefore has a physical-reflex input in the actuation path, but the semantic moral filter and values ranker do not control the wheels.

---

## 2. System Architecture

```text
┌────────────────────────────────────────────────────────────────────────────┐
│        PLANNERS / LLMs / BEHAVIOR TREES  (untrusted proposers)             │
└───────────────┬─────────────────────────────────────────┬──────────────────┘
                │ candidate actions / text instructions   │ wheel-speed proposals
                ▼ DELIBERATION PATH (advisory)            ▼ ACTUATION PATH
   ┌─────────────────────────────┐             ┌─────────────────────────────┐
   │ QERRA-HSR API input         │             │ Layer 1A SUPERVISORY GATE   │
   │ Layer 2   SEMEV-12          │             │ gate_core.py v0.4           │
   │ Layer 3   QERRA-THRIVE      │             │ + ROS 2 qerra_gate_node     │
   └─────────────────────────────┘             │ + lidar / proposer watchdog │
                                               │ + Layer 1B HSR UDP :5008    │
                                               │   telemetry / HsrReceiver  │
                                               └──────────────┬──────────────┘
                                                              │ constrained wheel command
                                                              ▼
                                                       BASE CONTROLLER
                                                              │
                                                              ▼
                                                        wheel motors

       Layer 1B QERRA-HSR reflex status also enters the Gate over UDP :5008.
       Layers 2 and 3 remain advisory and do not hold wheel authority.
```

### Layer 1A: Supervisory Gate Core v0.4 (Actuator Authority)

* **Directory and files:** `gate/` (Apache-2.0), `verify_log.py`, `controllers/tiago_supervisory_gate/` (Webots controller), `worlds/` (Webots scenarios), `ros2/qerra_gate_node.py` v0.3.1, and `launch/qerra_gate.launch.py`.
* **Modules:**
  - `gate_core.py` — pure function `step(state, params, inputs) -> StepResult`. Standard library only; no sockets, files, Webots, clock or randomness. Time arrives as an explicit integer input in microseconds.
  - `gate_config.py` — live parameter factory, including the rate-derived `dt_us` and `max_tick_gap_us = 2 * dt_us`.
  - `gate_ipc.py` — non-blocking UDP receiver for the Webots IPC path. Drain is bounded to 256 datagrams per call, messages are capped at 2048 bytes, and payloads are strictly parsed.
  - `gate_lidar.py` — `CorridorFilter`: projects lidar samples into the configured forward corridor and replaces valid samples outside it with `+inf`. Invalid values are not converted into clear readings.
  - `gate_link.py` — gate-to-proposer simulation-time channel.
  - `hsr_telemetry.py` v0.4.0 — mandatory HSR wire-packet parser, integer-permille classifier and pure `step_hsr_stream()` sequence/freshness monitor.
  - `gate_log.py` — SHA-256 hash-chained flight recorder with deterministic replay support.
* **Units:** integers in the decision/log core — time in microseconds, wheel speed in microradians per second, distance in millimetres.
* **Parameters:** held in immutable `GateParams` (validated on construction). Inputs cannot mutate the parameter record.
* **Authority rules:** the Gate is the only process that writes simulated wheel velocities in the Webots controller. A proposal can only be clamped down into the configured envelope, never raised. In ROS 2, the base controller must be configured to accept commands only from the Gate output topic; ROS graph naming and remapping alone do not establish exclusive authority.
* **Stopping envelope:**

  ```text
  d_stop(v) = ceil(v^2 / (2 * a_design))
            + ceil(v * t_react / 1e6)
            + margin
  ```

  The envelope uses `a_design = 500 mm/s^2` (0.5 m/s²), reaction time `t_react` in microseconds, and `margin = 300 mm`. At 196 mm/s, the configured envelope is 346 mm with the Webots 32 ms reaction allowance, 358 mm in the ROS 2 simulation profile (96 ms), and 371 mm in the 10 Hz Hokuyo scanner profile (160 ms). These are configured software envelopes, not measured physical stopping guarantees.
* **AR-2 reverse clamping:** Option A is symmetrical. With `w_min_urad_s = 0`, if either wheel requests reverse rotation, both wheel outputs are clamped to `(0, 0)`. This is a command-envelope clamp, not a separate trip. `Reason.PASS` means that no trip fired on that tick; it does not mean that the proposal passed through unchanged.
* **Phase 1 non-finite Twist inhibition:** `GateInputs.proposal_invalid` and `GateState.proposal_inhibited` represent rejected non-finite ROS `Twist` proposals. The adapter flags NaN or ±Inf in `linear.x` / `angular.z`; Gate Core emits `Event.MSG_REJECTED_INVALID`, sets `proposal_inhibited=True`, and commands `(0, 0)` in `Mode.RUN` on that tick. The invalid proposal does not refresh the held proposal timestamp. A fresh valid Twist clears the temporary inhibition; otherwise the existing 150 ms proposer watchdog escalates to `TRIP_PROPOSER_STALE`. This inhibition does not clear an existing `TRIPPED` or `AWAITING_RESET` state.
* **Modes:** `RUN`, `TRIPPED`, `AWAITING_RESET`. The Gate starts `TRIPPED` (fail-closed). A node-level `FAULT` is a separate process-lifetime `NodeFaultLatch` overlay, not a fourth Gate Core mode.
* **Trip reasons:** `TRIP_LOG_FAILURE`, `TRIP_SENSOR_INVALID`, `TRIP_OBSTACLE`, `TRIP_PROPOSER_DEAD`, `TRIP_PROPOSER_STALE`, `TRIP_CLOCK_ANOMALY`, `TRIP_HSR_CRITICAL`, `TRIP_HSR_INVALID`, and `TRIP_HSR_STALE`.
* **Lidar validation:** the scan must have the expected sample count and be fresh; invalid values (NaN, non-positive or non-numeric) are rejected. The live configuration requires `min_raw_lidar_returns >= 5` across the 240-degree scan. An all-`+inf` scan has no finite raw returns and trips `TRIP_SENSOR_INVALID`; it is not treated as a valid clear scan.
* **HSR telemetry contract and receiver diagnostics:** `gate/hsr_telemetry.py` v0.4.0 requires all six wire fields: `obs_id`, `t_obs_us`, `t_emit_us`, `distress_permille`, `hazard_proximity`, and `persons_nearby_count`. Omitting either contextual field is rejected; there are no fail-open parser defaults. `step_hsr_stream()` detects repeated-frame freeze and counter/timestamp regression. Controlled rebase requires at least five qualifying packet-bearing control ticks (maximum one credit per poll) and at least 160 ms of observation-time dwell. `HsrReceiver` preserves monotonic lifetime drained/rejected counters across `reset()` and exposes fixed sanitized rejection categories bounded to 64 characters; `/gate/state` publishes `hsr_drained_total`, `hsr_rejected_total` and `hsr_last_rejection_reason`, alongside freeze/rebase diagnostics. `MONITOR` imposes no velocity cap in `Mode.RUN`; it blocks clear-dwell completion and operator reset while latched in `TRIPPED` or `AWAITING_RESET`.
* **Recovery contract:** after a trip, the Gate remains latched until the relevant hazard is clear for a continuous 1.0 s dwell and an explicit operator reset is accepted. The accepted-reset tick remains quiescent and commands zero; motion can resume on a subsequent eligible `RUN` tick.
* **Default Webots/ROS 2 parameters:**

  | Parameter | Value |
  |-----------|-------|
  | Control tick (`dt_us`) | 32,000 µs at 31.25 Hz (nominal) |
  | Proposer freshness limit (`t_watch_us`) | 150,000 µs (150 ms) |
  | HSR freshness limit (`t_hsr_stale_us`) | 96,000 µs (96 ms) |
  | Lidar freshness limit | 96,000 µs in the simulation profile; 300,000 µs in the stated 10 Hz scanner profile |
  | Reaction allowance (`t_react_us`) | 32,000 / 96,000 / 160,000 µs (Webots / ROS 2 simulation / 10 Hz Hokuyo profiles) |
  | Continuous-clear dwell (`t_dwell_us`) | 1,000,000 µs (1.0 s) |
  | Maximum tick gap (`max_tick_gap_us`) | `2 * dt_us`: 64,000 µs at 31.25 Hz; 200,000 µs at 10 Hz |
  | Design deceleration (`a_design_mmps2`) | 500 mm/s² |
  | Safety margin (`margin_mm`) | 300 mm |
  | Wheel radius | 98 mm (TIAGo base) |
  | Wheel speed envelope | 0 to 3,000,000 µrad/s (3.0 rad/s), capped by the motor maximum in the controller; no reverse |
  | Lidar | Hokuyo baseline, 682 samples in the ROS 2 default profile; Webots TIAGo scan: 667 samples; 240° field of view and 0.32 m corridor half-width |

* **Flight recorder:** the canonical JSONL records are chained using `hash = SHA256(prev_hash || canonical_bytes)`, starting from a 64-zero genesis hash. `gate_log.py` persists `obstacle_breach`, `hsr_status`, `hsr_age_us`, and `proposal_invalid` in the relevant record inputs/fields and supports bit-for-bit offline replay via `verify_log.py --replay`. Demo 7 (`RUN_1791713619`) and Demo 9 (`DEMO9_SCENARIO_B_FINAL`) have recorded evidence; Demo 9's historical run was produced with Gate v0.3 and has been replayed through Gate Core v0.4. In `qerra_gate_node`, an enabled flight-log append/flush/`fsync` failure produces `TRIP_LOG_FAILURE` and zero software command output on the same control tick (R-10). The hash chain is tamper-evident relative to a trusted anchor; the node does not independently anchor its head hash.

### Layer 1B: QERRA-HSR v0.1 (Physical / Social Reflex)

* **Directory:** `hsr/` (Apache-2.0).
* **Properties:** Pure Python, standard-library classifier; zero ML in this classifier. Invalid, missing or out-of-range evaluator input (including `None`, NaN, Inf, wrong types or negative person counts) fails closed to `CRITICAL` in the evaluator.
* **Vectors (3):** `immediate_physical_distress`, `human_isolation`, `environmental_hazard_proximity`.
* **Thresholds:** distress confidence ≥ 0.75 gives `CRITICAL`; ≥ 0.45 gives `MONITOR`; person isolation means nearby-person count ≤ 1 and contributes to `CRITICAL` only with a distress signal. These are author-chosen engineering / ODD placeholders, not validated biometric thresholds.
* **Output:** `CLEAR`, `MONITOR`, or `CRITICAL`, with reasoning and a `recovery_directive`. `CRITICAL` suspends SEMEV-12 in the API pipeline and trips the Supervisory Gate when valid HSR telemetry reaches the actuation path. `robot_task_interruptible` affects the recovery directive, not whether a critical condition is classified.
* **Stabilizer:** `hsr/hysteresis_wrapper.py` (`StabilizedHSR`) holds an elevated status until a calmer reading has persisted for a 1.0 s dwell.
* **Wire / Gate semantics:** the ROS wire contract carries integer `distress_permille`, `hazard_proximity` and `persons_nearby_count`; it does not carry `robot_task_interruptible` or natural-language recovery directives. `MONITOR` does not cap velocity during active `Mode.RUN`. It blocks recovery dwell completion and operator reset while the Gate is latched.

### Layer 2: SEMEV-12 v1.9.2 (Moral Deliberation Engine)

* **Files:** `ethical_core.py`, `vectors.py`.
* **Properties:** Multi-anchor max-pooling (`all-MiniLM-L6-v2`) combined with deterministic regex mechanisms: pattern fallbacks, a v005 direct-negation pre-filter (`_v005_negation_guard`), hardened safety-override paraphrase patterns, and an absolute severe-harm veto.
* **Vectors (12):** `v001` through `v012` (coherence protection, family severance, survival instinct, moral pressure, harm intent, family origin chain, personal potential, shallow remorse, ethical severance, cognitive manipulation, autonomy violation, institutional trust).
* **Output:** `decision: safe` (score ≤ 0.5) or `decision: modified` (score > 0.5). A `modified` decision blocks the Behavior Tree condition. Advisory with respect to wheel authority: SEMEV-12 is not part of the safety function.

### Layer 3: QERRA-THRIVE v2.0.0 (Values Companion Layer & Action Ranker)

* **Directory:** `values/`.
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

The actuation and deliberation paths use separate budgets:

| Budget | Value | Where | Purpose |
|--------|-------|-------|---------|
| Gate control tick | 32 ms default (31.25 Hz) | ROS 2 node; Webots uses 32 ms tick | One Gate evaluation per tick |
| Reaction allowance (`t_react_us`) | 32 / 96 / 160 ms profiles | Gate configuration | Configured allowance in the stopping envelope; not a measured WCET or physical latency |
| Proposer freshness | 150 ms | `gate_core.py` (`t_watch_us`) | Stale or absent proposals trip the Gate |
| Lidar freshness | 96 ms simulation; 300 ms 10 Hz scanner profile | Gate configuration | Stale scans trip the Gate |
| HSR freshness (`t_hsr_stale_us`) | 96 ms | `gate_core.py` | Stale required HSR telemetry trips the Gate |
| Maximum inter-tick gap | `2 * dt_us` | `gate_config.py` / `qerra_gate_node` | Bounds accepted continuous-dwell tick gaps |
| Clear dwell before reset | 1.0 s | `gate_core.py` | Continuous clear time before operator reset can be accepted |
| HSR stabilizer dwell | 1.0 s | `hsr/hysteresis_wrapper.py` | Holds an elevated evaluator status until calm readings persist |
| Remote API timeout | 800 ms | `ros2_bridge.py` (`API_TIMEOUT_SECONDS`) | Remote SEMEV-12 call; on timeout/network error the bridge falls back to the local model |

The 800 ms figure is a remote-call timeout on the deliberation path. It is not a wheel-level watchdog.

---

## 3. Behavior Tree Integration & Nodes

QERRA-v2 Classical provides two dedicated PyTrees Behavior nodes:

1. **`QerraConditionNode` (`qerra_condition_node.py` / `qerra_standalone_remote_node.py`):**  
   Non-blocking Condition node evaluating Layer 1B (QERRA-HSR) and Layer 2 (SEMEV-12) through the advisory path. It returns `RUNNING` while evaluation is pending, `SUCCESS` only when the goal is accepted, the result succeeds and the decision is `safe`, and `FAILURE` otherwise. Missing or malformed HSR telemetry is forwarded as invalid values so the bridge fails closed.
2. **`QerraActionRankerNode` (`qerra_action_ranker_node.py`):**  
   Non-blocking Action Ranker leaf node evaluating Layer 3 (QERRA-THRIVE) candidate action choices. Uses decision-point caching (`_dirty = True`) to execute sentence-transformer encodings (~25 ms CPU) only when candidates change, preserving sub-millisecond tick speeds during routine ticks.

**ROS 2 bridge (`ros2_bridge.py`):**
* Standalone mode (no ROS 2) runs a direct local evaluation. With `rclpy` and the experimental `qerra_msgs` interface explicitly available in a local workspace, it can be used as an Action Server on `/qerra/evaluate` (`qerra_msgs/action/QerraEvaluate`), running on a `MultiThreadedExecutor` with a `ReentrantCallbackGroup`.
* Layer 1B is evaluated locally, with `StabilizedHSR` thread-safe wrapping. Missing, `None` or malformed evaluator telemetry returns a fail-closed critical result.
* Layer 2 is hybrid: remote API first with the 800 ms timeout, then a locally pre-loaded SEMEV-12 model as fallback.

---

## 4. Interaction Between Layers

### Actuation path
* The Supervisory Gate evaluates untrusted wheel proposals and is the only process that writes simulated wheel commands in the Webots supervisory-controller topology. In ROS 2, it publishes the designated constrained output; the deployment must prevent alternate publishers from bypassing that output.
* The Gate evaluates lidar, proposal freshness, timing and Layer 1B HSR telemetry. A required HSR `CRITICAL`, invalid stream state or stale heartbeat can trip the Gate.
* The Gate can clamp a proposal down or inhibit it, never increase it. Layers 2 and 3 do not command wheels through the Gate today.

### Deliberation path

The advisory execution sequence before a robot commits to a text-described action:

```text
[1. Layer 1B QERRA-HSR (API reflex check)] ──► [2. Layer 2 SEMEV-12 (Moral Gate)] ──► [3. Layer 3 THRIVE (Action Ranker)] ──► [Selected action]
Local contextual check                         Filters coercive/harmful candidates      Ranks surviving candidates                 Advisory result
```

**Core Interaction Rules:**
* QERRA-HSR `CRITICAL` suspends SEMEV-12 deliberation and Layer 3 action ranking in the API pipeline. In the separate actuation path, valid HSR `CRITICAL` telemetry trips the Supervisory Gate.
* A SEMEV-12 `modified` decision is never overridden by Layer 3 advisory rankings.
* The deliberation layers run in strict sequence (HSR → SEMEV-12 → THRIVE); each layer narrows what the next layer sees.
* Human physical or medical emergencies outrank Layer 3 advisory spatial or ecological courtesy via an explicit `EMERGENCY_BOOST = 0.35`.

---

## 5. Repository Package Structure

Key files and directories (selected architecture and verification paths):

```text
QERRA-v2-classical/
├── gate/                                      # Layer 1A: Supervisory Gate Core v0.4 (Apache-2.0)
│   ├── gate_core.py                           # pure-function state machine (stdlib only)
│   ├── gate_config.py                         # live parameters / rate-derived timing
│   ├── gate_ipc.py                            # non-blocking UDP IPC receiver
│   ├── gate_lidar.py                           # forward-corridor lidar filter
│   ├── gate_link.py                            # gate/proposer simulation-time channel
│   ├── gate_log.py                             # SHA-256 flight log and replay schema
│   └── hsr_telemetry.py                        # HSR wire contract v0.4.0 and stream monitor
├── hsr/                                       # Layer 1B: QERRA-HSR v0.1 (Apache-2.0)
│   ├── qerra_hsr.py                            # deterministic 3-vector evaluator
│   └── hysteresis_wrapper.py                   # StabilizedHSR
├── ros2/                                      # ROS 2 Jazzy adapter (Apache-2.0)
│   ├── qerra_gate_node.py                      # qerra_gate_node v0.3.1
│   └── hsr_receiver.py                         # UDP HSR receiver / diagnostics
├── launch/
│   └── qerra_gate.launch.py                   # 14 typed parameters + 5 Pattern B remappings
├── src/qerra_msgs/
│   └── COLCON_IGNORE                          # masked from standalone qerra_core colcon build
├── scripts/
│   ├── untrusted_proposer.py                  # Webots Demo 7 proposer
│   └── synthetic_hsr_producer.py              # synthetic ROS 2 HSR telemetry producer
├── controllers/tiago_supervisory_gate/        # Webots supervisory controller
├── worlds/                                    # Webots Demo 7–9 worlds
├── results/                                   # simulation logs and anchors
├── verify_log.py                              # offline flight-recorder verifier
├── values/                                    # Layer 3 QERRA-THRIVE v2.0.0 (Apache-2.0)
│   ├── __init__.py
│   ├── thrive_vectors.py
│   ├── human_centered/                         # Suite A (Vectors 1–9)
│   └── ecological/                             # Suite B (Vectors 10–12)
├── ethical_core.py                            # Layer 2 SEMEV-12 v1.9.2 (Apache-2.0)
├── vectors.py                                 # SEMEV-12 vector definitions
├── app.py                                     # FastAPI reference application
├── qerra_condition_node.py                    # advisory Layer 1B/2 PyTrees Condition node
├── qerra_action_ranker_node.py                # advisory Layer 3 PyTrees Action Ranker
├── qerra_standalone_remote_node.py            # Condition node calling live API over HTTP
├── demo_thrive_bt.py                          # master 12-vector PyTrees BT demo
├── ros2_bridge.py                             # separate advisory ROS 2 bridge entry point
├── tests/
│   ├── test_hsr_conformance.py                # 28,028-case v0.4.0 parity sweep (8 tests)
│   ├── test_hsr_receiver_diagnostics.py       # monotonic UDP diagnostics (8 tests)
│   ├── test_adversarial_hsr.py                # two executable HSR exploit demonstrations
│   └── test_gate_ros2_*.py                    # ROS 2 node, traffic, wiring, remapping and exterior tests
├── .github/workflows/
│   ├── tests.yml                              # host/unit, HSR, license and SEMEV regression CI
│   └── ros2_jazzy.yml                         # native ROS 2 Jazzy container integration CI
├── package.xml / setup.py                     # qerra_core 2.4.1, ament_python, Apache-2.0
├── LICENSE                                    # Apache License 2.0
├── NOTICE                                     # copyright and attribution notices
├── SAFETY_CONCEPT.md                          # v0.11
├── TECHNICAL_BRIEF_ROS2_GATE.md               # v1.6.0
├── QERRA-HSR-Design-v0.1.md                   # HSR design and non-claims
├── LIMITATIONS.md                             # current engineering limitations
├── README.md                                  # project entry point
└── CHANGELOG.md                               # version and milestone history
```

### Licensing map

**The entire repository is licensed under Apache-2.0**, including `gate/`, `hsr/`, `ros2/`, `values/`, SEMEV-12, QERRA-THRIVE and `verify_log.py`. Earlier mixed-license descriptions are obsolete and do not describe the current repository licence.

| Component | Current license |
|-----------|-----------------|
| `gate/` (Layer 1A) | Apache-2.0 |
| `hsr/` (Layer 1B) | Apache-2.0 |
| `ros2/` and `launch/` | Apache-2.0 |
| `values/` (Layer 3) | Apache-2.0 |
| SEMEV-12 (`ethical_core.py`, `vectors.py`) | Apache-2.0 |
| `verify_log.py` | Apache-2.0 |
| Tests and supporting repository code | Apache-2.0, subject to repository notices |

`tests/test_license_boundary.py` verifies repository-wide license/version boundary parity and standard-library isolation checks. The current repository-wide licensing statement is Apache-2.0.

### Packaging

`qerra_core` is package metadata version **2.4.1**, built with `ament_python`, ROS package format 3 and Apache-2.0. It is a standalone package and does not depend on `qerra_msgs`. The experimental `src/qerra_msgs/` subtree is masked from colcon discovery by `src/qerra_msgs/COLCON_IGNORE` and excluded from the root `package.xml` dependencies and the current Jazzy build. Console entry points include `qerra_gate_node` and `bridge`. The `qerra_msgs` action interface is not generated or tested by the standalone `qerra_core` CI workflow.

### Continuous Integration

The 17 November 2026 baseline is commit `027438a` on `main`. Package metadata remains 2.4.1; no new Git release tag is asserted for these updates.

* **Host CI** (`.github/workflows/tests.yml`, Ubuntu Python 3.10, Run #857): runs `python -m unittest discover -s tests -p "test_*.py"` — **257 collected (243 passed, 14 cleanly skipped without `rclpy`, 0 failures)**, plus **20 HSR tests** under `hsr/`, **15 SEMEV-12 regression cases**, and `tests/test_license_boundary.py`.
* **Native ROS 2 Jazzy CI** (`.github/workflows/ros2_jazzy.yml`, official `ros:jazzy` container, Run #122): builds standalone `qerra_core` and runs **43 container integration tests** across six modules: `21 + 8 + 5 + 4 + 1 + 4`.

The 14 host skips are ROS-dependent tests that cannot run on a host without `rclpy`: 5 live-traffic tests, 4 dual-protocol/node-regression tests, 1 remapping test and 4 Nav2-compatible exterior tests. The 43 native Jazzy tests comprise 21 `test_gate_ros2_node.py`, 8 `test_gate_ros2_node_wiring.py`, 5 `test_gate_ros2_live_traffic.py`, 4 `test_gate_ros2_dual_protocol.py`, 1 `test_gate_ros2_remapping.py`, and 4 `test_gate_ros2_nav2_exterior.py` tests. The license/version boundary guard is part of host CI. These results are software/CI evidence, not physical robot validation or a real-time guarantee.

---

## 6. Current Limitations

**Platform and evidence boundary**
* Development and simulation use Webots R2025a on Windows 11; ROS 2 integration is built and exercised in native ROS 2 Jazzy Linux CI containers. The project has not been tested on physical hardware.
* The host is not an RTOS. Python execution, ROS 2 scheduling, DDS delivery, disk I/O and actuator response do not have established worst-case execution-time (WCET) bounds. Green CI does not establish hard real-time behaviour.
* The Webots evidence is simulation evidence. It does not establish real sensor performance, physical motor braking, hardware timing or safety certification.

**Layer 1A Supervisory Gate**
* **Commanded, not measured, velocity:** `d_stop` uses commanded wheel speed. Simulated wheel telemetry has shown periods where measured wheel rotation and commanded speed disagreed (consistent with caster drag or slip, an attribution not isolated by a separate experiment). Physical integration needs measured velocity and braking data.
* **Rotational sweep is unmodelled:** the corridor filter models forward translation only. It does not calculate the full swept footprint during a pivot or curved trajectory; a nearby side obstacle can therefore be outside the current forward-corridor approximation.
* **Single-threaded executor assumption:** `QerraGateNode` relies on the default `SingleThreadedExecutor` / `rclpy.spin(node)` callback serialization and has no mutex locks around shared callback state. Running callbacks concurrently in a `MultiThreadedExecutor` without suitable mutually exclusive callback-group protection would introduce read/write race risks for `_latest_proposal`, `_latest_ranges` and `_reset_requested`.
* **Localhost trust boundary:** UDP channels and ROS 2 topics are unauthenticated. A local process able to publish to the base command topic can bypass the Gate; the current design assumes a trusted local process boundary and does not provide SROS2 access control or sender authentication.
* **Two executable adversarial exploits:** `tests/test_adversarial_hsr.py` demonstrates masked-distress re-arm using forged unauthenticated telemetry and ingestion crowding where a burst exceeding the 256-datagram per-poll limit delays a trailing `CRITICAL` packet. These are known residual risks, not protections.
* **`Twist` has no source timestamp:** proposals are stamped when received by the node. The 150 ms watchdog detects lack of fresh messages at the Gate, not planner computation age before publication.
* **Rapid valid/invalid proposal chattering:** alternating `VALID -> NaN/Inf -> VALID` proposals can repeatedly inhibit and restore output while valid proposals refresh the held timestamp. There is no separate chattering debounce. A zero command remains a software setpoint, not a physical stop.
* **Zero command and downstream behaviour:** `0.0` `Twist` is not an emergency stop, mechanical brake or hardware STO. If the node dies or stops ticking, a downstream controller may hold its last command unless it has its own independently configured and tested timeout or safety function.
* **Lidar metadata and coverage:** the current callback validates beam count and data values but does not fully validate `LaserScan` angular metadata, frame transforms or all sensor-acquisition properties. The forward corridor is not full-body or rearward protection. The `min_raw_lidar_returns >= 5` check is a global scan-liveness condition, not proof that the forward sector is visible.
* **Timing values are configured estimates:** the Webots 32 ms, ROS 2 96 ms and 10 Hz scanner 160 ms reaction allowances are not measured worst-case bounds. Sensor acquisition, transport, executor delay, OS scheduling, motor-controller response and braking require measurement on the target hardware. The 96 ms HSR freshness watchdog is a separate configured bound.

**Layer 1B QERRA-HSR**
* **ODD placeholder thresholds:** HSR thresholds (0.45 / 0.75 normalized score, mapped to 450 / 750 permille, and `ISOLATION_COUNT_THRESHOLD = 1`) are author-chosen engineering placeholders. They have not been validated against any human population, posture, gait or sensor data. ODD profiles are configuration slots; only the default profile is exercised in simulation and CI. No claim is made about real-distress detection, false-alarm rate or miss rate. The Layer 1B wire packet carries no metric distance to the human subject.
* **`MONITOR` Mode.RUN behaviour:** `MONITOR` imposes no velocity cap in active `Mode.RUN`. The current 3.0 rad/s wheel envelope at a 98 mm radius bounds nominal wheel-derived linear speed at 0.294 m/s; the HSR packet does not contain person-distance metrics needed to justify Speed and Separation Monitoring. While latched in `TRIPPED` or `AWAITING_RESET`, `MONITOR` blocks clear-dwell completion and operator reset (`RESET_REJECTED_HAZARD`).
* **Black-channel contradictory-frame drop scope:** malformed or contradictory frames (for example, a `state_mismatch`) are dropped and counted as receiver rejections; they do not immediately latch `TRIP_HSR_INVALID`. If valid `CLEAR` frames continue to be accepted between contradictory frames, the held `CLEAR` status remains available until valid frames cease and the 96 ms HSR staleness watchdog expires. The receiver's rejection counter and category provide diagnostics, not immediate trip semantics for every rejected datagram.
* **No metric person distance or validated perception:** HSR consumes externally supplied distress, person-count and hazard signals. It does not itself perform live human perception or calculate metric distance/time-to-collision. The thresholds and signal semantics have not been human-subject or sensor validated.
* **Stream monitor limits:** sequence and timestamp checks cannot prove that a producer is obtaining genuinely new sensor frames if it continues to emit fresh counters and timestamps over stale content. UDP sender identity and timestamps are unauthenticated; producer and Gate clock domains must be compatible.

**Regulatory boundary**

QERRA-v2 Classical is an unrated supervisory software research prototype. It is not certified under the EU Machinery Regulation (EU) 2023/1230 and provides no ISO 13849-1 Performance Level or IEC 62061 / IEC 61508 Safety Integrity Level rating. Any physical deployment must operate upstream of, and subordinate to, independently specified and appropriately certified emergency-stop, protective-sensing and Safe Torque Off (STO) functions. The standards are reference frameworks, not evidence of compliance.

---

## 7. Architecture Decision Records and Design Documents

| ADR | Title | Status |
|----------------|----------------------------------------------------|----------|
| ADR-001 | Creation and Design of SEMEV-12 Ethical Framework | Accepted |
| HSR-ADR-001 | Three-Vector Design Decision for QERRA-HSR v0.1 | Accepted |

There is no separate ADR for the Supervisory Gate. Its principal design record is `SAFETY_CONCEPT.md` (**v0.11**, aligned to the 17 November 2026 baseline), covering claims and non-claims, hazards, parameters and architecture rules. The supporting engineering documents are:

* `TECHNICAL_BRIEF_ROS2_GATE.md` (**v1.6.0**) — ROS 2 Jazzy systems-engineering brief for the supervisory Gate and HSR integration.
* `QERRA-HSR-Design-v0.1.md` — Layer 1B vector definitions, activation logic, formal properties and perception/ODD non-claims.
* `LIMITATIONS.md` — known implementation, timing, security and physical-validation boundaries.
* `README.md` and `CHANGELOG.md` — project overview and dated implementation history.

---

*This document reflects the architecture as of November 2026 (qerra_core 2.4.1 / Gate Core v0.4).*
