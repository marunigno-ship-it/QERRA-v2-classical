<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright (c) 2026 Marussa Metocharaki -->

# QERRA Supervisory Gate & Assistive Reflex — Safety Concept

| | |
|---|---|
| Document version | 0.10 (ROS 2 Supervisory Gate & Layer 1B Stream Monitor Parity) |
| Date | 2026-11-05 |
| Author | Marussa Metocharaki |
| System under demonstration | QERRA Supervisory Gate & QERRA-HSR Reflex Companion (Pure Python Core v0.4, ROS 2 Jazzy Node v0.3.1, Webots R2025a TIAGo simulation, Windows 11 host, Ubuntu Linux CI container) |
| Status vocabulary | **SPECIFIED** (written, nothing built) → **IMPLEMENTED** (code exists, unit-tested) → **VERIFIED** (evidenced by live simulation run ID + anchored head hash or executed adversarial tests) |

**Historical Baseline Anchors:**
* **Demo 7 Baseline (Kinematic Lidar Stop):**
  * **Run ID:** `RUN_1791713619`
  * **Gate Version:** `0.2` (per `results/RUN_1791713619/ANCHOR.txt`)
  * **Verified Records:** 1,485 continuous ticks ($t = 0.032\text{ s}$ to $t = 47.520\text{ s}$)
  * **Cryptographic Head Seal:** `ae37ae62227c4fdca51233b7e4189607898ae2c27eca5bf0847414d1f0d4c191`
* **Demo 9 Baseline (Acute Distress Reflex & Dual-Dwell Recovery):**
  * **Run ID:** `DEMO9_SCENARIO_B_FINAL`
  * **Gate Version:** `0.3` (per `results/DEMO9_SCENARIO_B_FINAL/ANCHOR.txt`)
  * **Verified Records:** 438 continuous ticks ($t = 0.032\text{ s}$ to $t = 14.016\text{ s}$)
  * **Cryptographic Head Seal:** `eccb0d85416cf4a651205f34f3cc0d9275bff6e2b3baa512e4b23dbef0c2714a`
* **Anchors vs. current code:** Both historical anchors were produced by Gate v0.2 / v0.3 without the stream monitor, ROS node packaging, or node flight logger. The Demo 9 log replays bit-for-bit through the pure Gate v0.4 core (`verify_log.py --replay`, 438 control cycles, 0 divergences, verified 2026-10-29).

---

## 1. Purpose and scope

This document specifies the safety concept for Layer 1 of the QERRA architecture, establishing authority separation, reflexive protection, and audit durability for mobile robots:

> Deliberation is an untrusted proposer. It may be late, wrong, or dead. The supervisory gate is the only authorized software path to the wheels. The default is stop. Acute physical and social hazards trigger an immediate reflex clamp before deliberation resumes.

In scope:
- **Layer 1A (Supervisory Gate):** Software setpoint clamp, dynamic kinematic stopping envelopes, watchdog liveness, operator-latched recovery, persistent node fault latching, and tamper-evident SHA-256 rolling flight logs.
- **Layer 1B (QERRA-HSR Reflex Companion):** Fast threshold companion evaluating acute distress, social isolation, and environmental hazard proximity under ISO 13482 principles, accompanied by an asynchronous UDP perception stream monitor enforcing sticky freeze detection and controlled rebase dwells.

Out of scope:
- High-level SLAM, path planning, computer vision inference, moral deliberative filtering (SEMEV-12), and values ranking (THRIVE).
- Hardware-certified Safety Integrity Levels (SIL) or Performance Levels (PL). QERRA is a simulation-based research prototype evaluated in Webots and ROS 2 Jazzy; it does not replace hardware Safe Torque Off (STO) relays, safety laser scanners, or certified safety PLCs.
- Exclusive actuator authority in ROS 2. ROS 2 does not enforce sole-publisher authority on `/cmd_vel_safe`. An unauthenticated local process can publish directly to base topics or bypass the Gate entirely.

**Informative references** (standards consulted as engineering guidelines only; QERRA is not certified under any standard): ISO 12100 (risk assessment), ISO 13849-1, IEC 62061, IEC 61508, ISO 10218-1/-2, ISO 13482, ISO 3691-4, EN 50159.

---

## 2. Claims and non-claims

| ID | Claim (what QERRA Layer 1 evidences) | Non-claim (explicit boundary) | Status | Evidence |
|---|---|---|---|---|
| **C-1 Authority separation** | In simulation, the gate process is the sole writer of the simulated wheel motor handles. In ROS 2, `QerraGateNode` bridges untrusted `/cmd_vel` to protected `/cmd_vel_safe`. | In ROS 2, DDS does not restrict publisher access. Any hostile or errant local process can publish directly to `/cmd_vel_safe`. True authority separation requires OS-level process isolation and SROS2. Does not replace hardware STO relays. | **VERIFIED** (Simulation) / **IMPLEMENTED** (ROS 2) | Run `RUN_1791713619`: Webots controller holds sole motor handles. Node wiring confirmed in `tests/test_gate_ros2_node_wiring.py`. |
| **C-2 Fail-closed command** | The gate commands 0.0 rad/s (0.0 m/s) on: proposer watchdog expiry, proposer disconnect, invalid lidar, range $\le d_{stop}$, HSR critical/invalid/stale telemetry, or flight log write failure. Issued within $\le 32\text{ ms}$. | A command of 0.0 rad/s is a software setpoint, not an emergency stop. Physical stopping distance depends on vehicle inertia, brake dynamics, and traction. "Command issued" is not "robot stopped". | **VERIFIED** (Decomposed below) | Decomposed into verified sub-claims C-2a..C-2f. |
| **C-2a Obstacle stop** | The gate commands 0.0 rad/s when minimum corridor range $\le d_{stop}$. Issued within 1 control tick ($32\text{ ms}$). | Stopping envelope assumes design deceleration $a_{design} = 500\text{ mm/s}^2$. If physical traction or deceleration falls below this, physical collision may occur. | **VERIFIED** | Run `RUN_1791713619`: Fired at $337\text{ mm}$ clearance; standstill reached at $301\text{ mm}$ ($36\text{ mm}$ coasting). Obstacle cart undisplaced at $X = 2.8\text{ m}$. |
| **C-2b Watchdog expiry** | The gate commands 0.0 rad/s when proposal age $\ge T_{watch}$ ($150\text{ ms}$). | In ROS 2, `Proposal` arrival time is stamped at node receipt because `geometry_msgs/Twist` lacks a header timestamp. Watchdog detects communication stalls, not upstream planner compute latency. | **VERIFIED** | Run `RUN_1791709882`: Watchdog trip recorded at $t = 12.51\text{ s}$. Confirmed in `tests/test_gate_ros2_node.py`. |
| **C-2c Proposer disconnect** | The gate commands 0.0 rad/s when the proposer crashes or stops sending (`TRIP_PROPOSER_DEAD`). | Process restarts require monotonic `session_id` to resume without lockout. | **VERIFIED** | Demo 8 (`DEMO8_VIDEO_1792575455`) & unit tests in `test_gate_ipc.py`. |
| **C-2d Invalid/stale lidar** | The gate commands 0.0 rad/s on missing, NaN, non-finite, blind, or stalled lidar data (`TRIP_SENSOR_INVALID`). In ROS 2, scans with mismatched beam counts are discarded fail-closed. | Sensor liveness relies on $\ge 5$ raw returns across 240° FOV. Ray distribution is global; side walls can satisfy liveness even if forward beams are obscured. | **VERIFIED** | Tests in `test_gate_lidar.py` and `test_gate_ros2_node_wiring.py`. |
| **C-2e Distress reflex stop** | The gate commands 0.0 rad/s within 1 control tick ($\le 32\text{ ms}$) when Layer 1B reports `CRITICAL` distress (`TRIP_HSR_CRITICAL`). | Tested with synthetic/injected distress vectors, not live edge ML vision. | **VERIFIED** | Demo 9 (`DEMO9_SCENARIO_B_FINAL`): Injected at $t = 4.000\text{ s}$ (Cycle 125); clamped to $0.000\text{ rad/s}$ with 0 added latency ticks. |
| **C-2f Flight log write failure** | Under Requirement R-10, any failure during log append, flush, or `os.fsync` immediately clamps actuator commands to 0.0 m/s on the current tick and trips the Gate to `TRIP_LOG_FAILURE`. | Synchronous `fsync` inside the 32 ms tick can introduce timer jitter on slow or saturated storage devices without throwing an error. | **VERIFIED** | `tests/test_gate_ros2_node.py` (`test_flight_logger_failure_trips_r10_fail_closed`). |
| **C-3 Tamper-evident flight log** | Every gate evaluation appends a canonical JSON line sealed with rolling SHA-256 digests ($hash = \text{SHA256}(prev\_hash + canonical\_bytes)$). Record 0 cryptographically binds the GateParams and harness manifest anchored to a genesis block of 64 zeros. | Offline tampering is detectable only against an externally anchored head seal. Log records gate software commands, not motor encoder ground truth. Head hash is not externally cross-notarized during runtime. | **VERIFIED** | Demo 7 (`RUN_1791713619`, seal `ae37...`) and Demo 9 (`DEMO9_SCENARIO_B_FINAL`, seal `eccb0d85...`). Offline replay verified bit-for-bit via `verify_log.py --replay`. |
| **C-4 Asynchronous IPC robustness** | Ingestion from non-blocking sockets enforces bounded drains ($\le 256$ datagrams/tick), size caps (2048 bytes), and strict schema parsing. Malformed JSON, non-finite values, and causality inversions are dropped fail-closed. | Windows 11 and standard Linux are not RTOSs; execution jitter can delay drains. Datagrams exceeding the 256-drain ceiling remain queued in the OS buffer. | **VERIFIED** | 12 tests in `test_gate_ipc.py`; burst and malformed injection tests in `test_gate_ros2_node_wiring.py`. |
| **C-5 Actuator fail-closed isolation** | In simulation, `zero_wheels` executes left and right wheel clamping in separate try-blocks. In ROS 2, `safe_twist` publishes 0.0 velocities. | Motor driver exceptions in ROS 2 hardware base controllers are outside Gate process boundaries. Base controller must implement its own command watchdog. | **VERIFIED** | Unit tests in `tests/test_controller_actuators.py`. |
| **C-6 Recovery contract** | After a trip, the gate latches. Wheels stay at zero until: hazard is clear, continuous dwell elapses, and explicit operator reset arrives from an authorized channel. Reset during hazard, dwell, or while HSR is `MONITOR`/`CRITICAL` is strictly rejected (`RESET_REJECTED_*`). | Does not replace physical lockout/tagout (LOTO). Reset channel authorization is string-based (`"operator"`), not cryptographically authenticated. | **VERIFIED** | Demo 9: Reset refused at $t = 5.024\text{ s}$ during distress (`RESET_REJECTED_HAZARD`); forged reset rejection verified in `tests/test_gate_ros2_node_wiring.py`. |
| **C-7a Dual-dwell stabilization** | Recovery from distress requires stacked dwell completion: upstream reflex stabilizer dwell ($1.0\text{ s}$) followed by Gate core clear dwell ($1.0\text{ s}$). | Availability cost: extends standstill recovery period by design; a single-sample sensor glitch causes a latched stop requiring full dwell and operator reset. Live Demo 9 evidenced only the direct `CRITICAL` to `CLEAR` path. | **VERIFIED** | Demo 9 (`DEMO9_SCENARIO_B_FINAL`): Distress cleared at $t = 7.008\text{ s}$; Gate dwell completed at $t = 9.056\text{ s}$ before reset accepted. |
| **C-7b Gate-level HSR clear dwell** | With `hsr_required=True`, the Gate core requires $1.0\text{ s}$ ($T_{dwell}$) of continuous fresh `CLEAR` telemetry to arm reset. `MONITOR`, `CRITICAL`, stale stamps, or tick gaps $> max\_tick\_gap\_us$ reset the dwell timer. | Enforced only when `hsr_required=True`. Availability cost: $\ge 1.0\text{ s}$ standstill after any transient reflex excursion. | **VERIFIED** | Unit tests in `tests/test_gate_hsr_clear_dwell.py` (8 tests); offline repro `qerra_gate_hsr.py`. |
| **C-7c Perception stream monitor & rebase dwell** | Layer 1B `step_hsr_stream` inspects all incoming UDP datagrams in arrival order before reduction. A repeated `obs_id` triggers sticky freeze. A counter regression triggers rebase dwell, requiring BOTH $\ge 5$ consecutive clean ticks AND $\ge 160\,000\ \mu\text{s}$ of elapsed observation time. During dwell or freeze, receiver outputs `(None, None)`, tripping `TRIP_HSR_INVALID` when `hsr_required=True`. | Detects sequence counter faults only. A frozen upstream sensor with an active publisher regenerating fresh counters and timestamps passes undetected. Dwell elapsed time is measured on producer timestamps ($t_{obs}$), not the Gate clock. | **VERIFIED** | Unit tests in `tests/test_gate_ros2_node.py` and `tests/test_hsr_stream_matrix.py` (6 tests). |
| **C-8 Proposer ratchet re-basing** | The `(session_id, seq)` ratchet binds only while a live proposal is held. When none is held, a fresh valid proposal re-bases the ratchet, preventing a single high-sequence datagram from permanently locking the proposal channel. | Localhost UDP is unauthenticated. A hostile local sender transmitting a higher `(session_id, seq)` on every tick supplants the legitimate proposer. Defence requires SROS2 or OS IPC permissions. | **VERIFIED** | `tests/test_gate_ratchet_rebase.py` (7 tests). |
| **C-9 Persistent Node Fault Latch** | In `QerraGateNode`, an unhandled tick exception trips `NodeFaultLatch`, locking the node permanently into `mode: "FAULT"`, holding 0.0 m/s wheel commands, and reporting root-cause diagnostics to `/gate/state`. | The latch is permanent for the node process lifetime. It cannot be cleared by `/gate/reset`. Automatic node respawning must be prohibited in system launch configurations, as process restart clears memory state. | **VERIFIED** | `tests/test_gate_ros2_node_latch.py` (6 tests). |
| **C-10 Adversarial Vulnerabilities (Non-Claims)** | (1) Masked-distress re-arm: If the legitimate producer is silenced, an unauthenticated local process can forge a regression, satisfy the 160 ms / 5-tick rebase dwell, satisfy the 1.0 s clear dwell, and send an operator reset, returning the Gate to `RUN`. (2) Ingestion crowding: A flood exceeding 256 datagrams/tick delays ingestion of a trailing `CRITICAL` packet across ticks. | QERRA does not claim security against malicious local processes. Localhost is an assumed trusted process boundary. Operational deployments must secure topics with SROS2 and isolate processes via Linux cgroups / containers. | **VERIFIED (Vulnerabilities demonstrated)** | `tests/test_adversarial_hsr.py` (2 executable exploit tests confirming both vulnerabilities). |

---

## 3. Definitions and parameters

### 3.1 Kinematic Stopping Distance Formula

The mathematical stopping distance envelope $d_{\text{stop}}(v)$ is computed as:
$$d_{\text{stop}}(v) = \left\lceil \frac{v^2}{2 \cdot a_{\text{design}}} \right\rceil + \left\lceil \frac{v \cdot t_{\text{react}}}{10^6} \right\rceil + margin$$

Where:
- $v$: Commanded body linear velocity in mm/s ($\text{speed\_mps} \times 1000$).
- $a_{\text{design}} = 500\text{ mm/s}^2$ ($0.5\text{ m/s}^2$).
- $margin = 300\text{ mm}$.
- $t_{\text{react}}$: Worst-case reaction time allowance in microseconds ($\mu\text{s}$).

**Envelope Values across Verified Profiles:**
- **At Physical Cruise Speed ($196\text{ mm/s}$ from $2.0\text{ rad/s} \times 98\text{ mm}$ wheel radius):**
  - Webots Simulation Controller ($t_{\text{react}} = 32\text{ ms}$): $d_{\text{stop}} = 39\text{ mm} + 7\text{ mm} + 300\text{ mm} = \mathbf{346\text{ mm}}$.
  - ROS 2 Simulation Profile ($t_{\text{react}} = 96\text{ ms}$): $d_{\text{stop}} = 39\text{ mm} + 19\text{ mm} + 300\text{ mm} = \mathbf{358\text{ mm}}$.
  - 10 Hz Hardware Hokuyo Profile ($t_{\text{react}} = 160\text{ ms}$): $d_{\text{stop}} = 39\text{ mm} + 32\text{ mm} + 300\text{ mm} = \mathbf{371\text{ mm}}$.
- **At Nominal Speed ($200\text{ mm/s}$):**
  - Webots Simulation Controller ($32\text{ ms}$): $d_{\text{stop}} = 40\text{ mm} + 7\text{ mm} + 300\text{ mm} = \mathbf{347\text{ mm}}$.
  - ROS 2 Simulation Profile ($96\text{ ms}$): $d_{\text{stop}} = 40\text{ mm} + 20\text{ mm} + 300\text{ mm} = \mathbf{360\text{ mm}}$.
  - 10 Hz Hardware Hokuyo Profile ($160\text{ ms}$): $d_{\text{stop}} = 40\text{ mm} + 32\text{ mm} + 300\text{ mm} = \mathbf{372\text{ mm}}$.

### 3.2 Operational Parameters and Timing Profiles

| Symbol | Meaning | Webots Controller Profile | ROS 2 Sim Profile (Node Default) | 10 Hz Hardware Profile (Hokuyo) |
|---|---|---|---|---|
| `dt` | Control loop cycle time | $32\text{ ms}$ ($31.25\text{ Hz}$) | $32\text{ ms}$ ($31.25\text{ Hz}$) | $32\text{ ms}$ ($31.25\text{ Hz}$) |
| `t_react_ms` | Reaction latency budget | $32\text{ ms}$ ($32\,000\ \mu\text{s}$) | $96\text{ ms}$ ($96\,000\ \mu\text{s}$) | $160\text{ ms}$ ($160\,000\ \mu\text{s}$) |
| `lidar_period_ms` | Lidar scan interval | $32\text{ ms}$ ($32\,000\ \mu\text{s}$) | $32\text{ ms}$ ($32\,000\ \mu\text{s}$) | $100\text{ ms}$ ($100\,000\ \mu\text{s}$) |
| `lidar_stale_ms` | Lidar staleness ceiling | $96\text{ ms}$ ($3 \times dt$) | $96\text{ ms}$ ($3 \times dt$) | $300\text{ ms}$ ($3 \times T_{\text{scan}}$) |
| `T_watch` | Proposal freshness limit | $150\text{ ms}$ | $150\text{ ms}$ | $150\text{ ms}$ |
| `T_hsr_stale` | Reflex freshness ceiling | $96\text{ ms}$ | $96\text{ ms}$ | $96\text{ ms}$ |
| `T_dwell` | Gate core clear dwell | $1.0\text{ s}$ ($1\,000\,000\ \mu\text{s}$) | $1.0\text{ s}$ ($1\,000\,000\ \mu\text{s}$) | $1.0\text{ s}$ ($1\,000\,000\ \mu\text{s}$) |
| `rebase_dwell` | Stream monitor rebase dwell | — | $\ge 5\text{ ticks} \land \ge 160\text{ ms}$ | $\ge 5\text{ ticks} \land \ge 160\text{ ms}$ |
| `lidar_n_expected` | Expected beam count | $667$ (TIAGo Webots) | $682$ (Hokuyo URG-04LX) | $682$ (Hokuyo URG-04LX) |
| `w_max` | Maximum wheel angular speed | $3.0\text{ rad/s}$ | $3.0\text{ rad/s}$ | $3.0\text{ rad/s}$ |
| `a_design` | Design deceleration | $500\text{ mm/s}^2$ | $500\text{ mm/s}^2$ | $500\text{ mm/s}^2$ |
| `margin` | Standstill clearance | $300\text{ mm}$ | $300\text{ mm}$ | $300\text{ mm}$ |
| `min_raw_lidar_returns` | Liveness raw return threshold | $5$ across 240° | $5$ across 240° | $5$ across 240° |
| `hsr_required` | Reflex enforcement flag | `True` | `True` | `True` |

**Startup Invariant Guard**:
In `QerraGateNode`, timing parameters must strictly satisfy:
$$\text{lidar\_stale\_ms} \ge 2 \cdot \text{lidar\_period\_ms} + \text{dt\_ms}$$
Configurations violating this invariant fail closed at startup with `ValueError`.

---

## 4. Architecture rules

- **AR-1 Software Actuator Authority**: In simulation, the gate owns the simulated wheel motor handles. In ROS 2, `QerraGateNode` has sole design authority to publish to `/cmd_vel_safe`.
- **AR-2 Proposal Clamping**: The proposer can only propose speeds within or below the Gate stopping envelope, never exceed it.
- **AR-3 Parameter Immutability**: Gate envelope parameters are fixed at startup and immutable during runtime.
- **AR-4 Channel Separation**: Operator reset (`/gate/reset` or UDP 5006) is isolated from motion proposal channels (`/cmd_vel` or UDP 5005).
- **AR-5 Non-blocking Ingestion**: All network and ROS subscriptions drain non-blocking. UDP receivers enforce a maximum drain bound of 256 datagrams per control cycle.
- **AR-6 Strict Payload Parsing**: Datagrams are capped at 2048 bytes, strictly typed (integer permille for distress, integer microseconds for timestamps), and reject NaN/Inf fail-closed.
- **AR-7 Lidar Geometric Validation**: Lidar returns are corridor-filtered through a 0.64 m swept envelope. In ROS 2, any scan whose beam count does not match `lidar_n_expected` is discarded fail-closed (`TRIP_SENSOR_INVALID`).
- **AR-8 Pure Core Engine**: `gate_core.py` is a pure function `step(state, params, inputs) -> StepResult` using standard library only with zero external dependencies. Monotonic time is passed in as an integer microsecond argument.
- **AR-9 Direct Envelope Hazard Check**: Hazard detection evaluates $d_{\text{stop}}(v)$ against the minimum valid corridor range.
- **AR-10 Layer 1B Reflex Integration Contract**:
  - `CRITICAL` reflex state immediately commands 0.0 rad/s and trips to `Mode.TRIPPED` (`TRIP_HSR_CRITICAL`) within $\le 32\text{ ms}$.
  - Stale reflex telemetry ($\text{age} > T_{hsr\_stale}$) trips `TRIP_HSR_STALE`.
  - When `hsr_required=True`, missing, None, or invalid reflex telemetry trips `TRIP_HSR_INVALID`.
  - With `hsr_required=True`, the Gate core requires $1.0\text{ s}$ of continuous fresh `CLEAR` reflex frames before arming reset. Resets during `MONITOR` or `CRITICAL` are rejected (`RESET_REJECTED_HAZARD`).
- **AR-11 Independent Actuator Clamping**: Velocity outputs clamp left and right wheels in isolated execution blocks, ensuring single-actuator driver faults do not cause asymmetric runaway.
- **AR-12 Persistent Node Fault Latch**: Any unhandled exception during the node's control cycle trips `NodeFaultLatch`, forcing permanent 0.0 m/s wheel output and diagnostic FAULT telemetry for the process lifetime.
- **AR-13 Flight Log Durability (Requirement R-10)**: When enabled (`flight_log_path != ""`), log writes execute synchronous disk flush and `os.fsync`. Any file system failure immediately clamps actuator commands to 0.0 m/s and trips `TRIP_LOG_FAILURE`.
- **AR-14 Controlled Stream Rebase**: Asynchronous UDP reflex streams are monitored for monotonicity. Repeated sequence counters trigger sticky freeze. Counter regressions trigger a dual-gate dwell requiring $\ge 5$ clean control ticks and $\ge 160\text{ ms}$ of advancing sensor time before valid reflex states can be restored.

---

## 5. Audit Log Specification (Schema Version 1)

When enabled, every gate control tick writes one canonical JSON line to `gate_audit.jsonl` using binary LF (`\n`):

| Field | Type | Description |
|---|---|---|
| `v` | int | Schema version (`1`) |
| `run_id` | string | Unique run identifier |
| `seq` | int | Monotonic record index ($0, 1, 2, \dots$) |
| `sim_time_us` | int | Integer microseconds of simulation or ROS clock time |
| `wall_ns` | int | Host system timestamp in nanoseconds |
| `state` | string | `RUN`, `TRIPPED`, `AWAITING_RESET` |
| `reason` | string | Decision reason (`PASS`, `TRIP_OBSTACLE`, `TRIP_PROPOSER_DEAD`, `TRIP_PROPOSER_STALE`, `TRIP_SENSOR_INVALID`, `TRIP_HSR_CRITICAL`, `TRIP_HSR_INVALID`, `TRIP_HSR_STALE`, `TRIP_LOG_FAILURE`, `TRIP_CLOCK_ANOMALY`, `LATCHED_DWELL`, `LATCHED_AWAIT_RESET`, `RESET_ACCEPTED`) |
| `events` | list[str] | Secondary events (`RESET_REJECTED_HAZARD`, `RESET_REJECTED_CHANNEL`, `RESET_REJECTED_NOT_READY`, `MSG_REJECTED_*`, etc.) |
| `proposal_seq` | int or null | Sequence number of active proposal |
| `proposal_age_us` | int or null | Proposal age in microseconds |
| `lidar_valid` | bool | Scan validity flag |
| `lidar_min_mm` | int or null | Minimum corridor obstacle distance |
| `d_stop_mm` | int | Commanded stopping distance envelope in mm |
| `obstacle_breach` | bool | Direct stopping envelope breach flag (`lidar_min_mm <= d_stop_mm`) |
| `hsr_status` | string or null | Live reflex status (`CLEAR`, `MONITOR`, `CRITICAL`, or `null`) |
| `hsr_age_us` | int or null | Age of reflex evaluation in microseconds |
| `cmd_left_urad_s` | int | Output command to left wheel ($\mu\text{rad/s}$) |
| `cmd_right_urad_s` | int | Output command to right wheel ($\mu\text{rad/s}$) |
| `inputs` | dict (optional) | Serialized tick inputs enabling exact offline replay |
| `manifest` | dict (optional) | Sealed in Record 0 (`seq=0`): run ID, gate version, parameters, and harness fault injection switches |
| `gate_version` | string | Gate Core engine release (`0.4`) |
| `prev_hash` | string | Hex SHA-256 digest of preceding record (Record 0 uses 64 zeros) |
| `hash` | string | `SHA256(prev_hash_ascii || canonical_bytes)` |

Offline replay via `verify_log.py --replay` validates cryptographic chain integrity and reconstructs `GateInputs` to verify bit-for-bit decision reproducibility.

---

## 6. Revision log

| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-10-10 | Initial specification. All items SPECIFIED. |
| 0.2 | 2026-10-12 | Evidenced run `RUN_1791713619` attached. Claims C-1, C-2, C-3, C-4, C-6 raised to VERIFIED. Parameter defaults synchronized to $150\text{ ms}$ and $500\text{ mm/s}^2$. |
| 0.3 | 2026-10-17 | Hardened supervisory gate under independent review findings F1-F8. Added reaction time allowance $t_{react}$ in $d_{stop}$ ($346\text{ mm}$ envelope). |
| 0.4 | 2026-10-18 | Epistemic truth alignment under findings V1-V11: verified deterministic offline replay via `verify_log.py --replay`; documented V5 simulated-only stale watchdog and V6 forward-arc occlusion boundaries. |
| 0.5 | 2026-10-27 | Integrated Layer 1B QERRA-HSR reflex companion under Demo 9 (`DEMO9_SCENARIO_B_FINAL`, 438 cycles, Head Seal `eccb0d85...`). Added Claim C-2e (Distress reflex stop $\le 32\text{ ms}$) and Claim C-7 (Dual-dwell stabilization). Hardened Claim C-6 recovery contract to reject reset when HSR is non-clear. |
| 0.6 | 2026-10-29 | Split Claim C-7 into C-7a (VERIFIED, Demo 9) and C-7b (IMPLEMENTED, Gate-level continuous HSR `CLEAR` dwell via `hsr_clear_since_us`). Added Claim C-8 (ratchet re-basing). Gate core bumped to v0.4. Demo 9 log replays bit-for-bit through v0.4. |
| 0.7 | 2026-10-30 | Packaged Gate v0.4 into standalone ROS 2 Jazzy node (`qerra_gate_node`). Enforced unified clock domain (`use_sim_time` compatible) and fixed startup geometric parameters (`lidar_n_expected=682`). |
| 0.8 | 2026-10-31 | Wired `HsrReceiver` into `qerra_gate_node` via UDP (worst-severity batch reduction). Added clock echo on UDP port 5007 (`gate_link.send_state()`). Enforced fail-closed scan discard on beam count mismatch. |
| 0.9 | 2026-11-01 | Implemented persistent `NodeFaultLatch` (Claim C-9) to hold 0.0 m/s fail-closed across tick exceptions. Integrated SHA-256 hash-chained flight logger into the ROS 2 node under Requirement R-10 (Claim C-2f), enforcing immediate actuator clamping and diagnostic telemetry override upon log write failure. Parameterized reaction latency ($t_{\text{react}}$) and lidar staleness ceilings. |
| 0.10 | 2026-11-05 | **Documentation Parity & Adversarial Verification:** Documented Layer 1B perception stream monitor (`step_hsr_stream`) enforcing sticky freeze detection and dual-gate rebase dwell ($\ge 5$ ticks and $\ge 160\text{ ms}$, Claim C-7c). Clarified timing profiles and stopping envelopes ($346\text{ mm}$ Webots controller, $358\text{ mm}$ ROS 2 simulation, $371\text{ mm}$ Hokuyo hardware). Formalized startup timing invariant guard. Added Claim C-10 documenting verified adversarial vulnerabilities (buffer crowding above 256 datagrams and masked-distress re-arm on unauthenticated localhost boundary). Bumped test baseline to 211 host tests. |
