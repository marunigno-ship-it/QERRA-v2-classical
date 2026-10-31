<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright (c) 2026 Marussa Metocharaki -->

# QERRA Supervisory Gate & Assistive Reflex — Safety Concept

| | |
|---|---|
| Document version | 0.8 (ROS 2 HSR Reflex Telemetry Integration & Fail-Closed Guard Hardening) |
| Date | 2026-10-31 |
| Author | Marussa Metocharaki |
| System under demonstration | QERRA Supervisory Gate & QERRA-HSR Reflex Companion, simulated PAL Robotics TIAGo in Webots R2025a, Windows 11 |
| Status vocabulary | **SPECIFIED** (written, nothing built) → **IMPLEMENTED** (code exists, unit-tested) → **VERIFIED** (evidenced by live simulation run ID + anchored head hash) |

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
* **Anchors vs. current code:** Both anchors were produced by Gate v0.2 / v0.3. The Gate core has since changed (v0.4: C-7b, C-8). The Demo 9 log replays bit-for-bit through the v0.4 core (`verify_log.py --replay`, 438 control cycles; author-run on the local branch, 2026-10-29), so its recorded decisions are unchanged. Demo 9 does not exercise the code paths those changes alter (see C-7b and C-8).

---

## 1. Purpose and scope

This document specifies the safety concept for Layer 1 of the QERRA architecture, establishing authority separation and reflexive protection on a mobile robot:

> Deliberation is an untrusted proposer. It may be late, wrong, or dead. The supervisory gate is the only path to the wheels. The default is stop. Acute physical and social hazards trigger an immediate reflex clamp before deliberation resumes.

In scope: 
- **Layer 1A (Supervisory Gate):** Exclusive motor actuator authority, dynamic kinematic stopping envelopes, watchdog liveness, operator-latched recovery, and tamper-evident SHA-256 rolling flight logs.
- **Layer 1B (QERRA-HSR Reflex):** Fast threshold companion evaluating distress, isolation, and environmental proximity under ISO 13482 principles, with hysteresis stabilization.

Out of scope: moral filtering (SEMEV-12), values ranking (THRIVE), high-level perception, autonomous SLAM navigation, payload dynamics, and certified hardware PL/SIL safety circuits.

This is a research prototype evaluated in Webots simulation. It is not an ISO-certified commercial safety controller.

Informative references (names only; clause numbers omitted until checked against purchased standards): ISO 12100 (risk assessment), ISO 13849-1, IEC 62061, IEC 61508, ISO 10218-1/-2, ISO 13482, ISO 3691-4.

---

## 2. Claims and non-claims

| ID | Claim (what QERRA Layer 1 evidences) | Non-claim (explicit boundary) | Status | Evidence |
|---|---|---|---|---|
| C-1 Authority separation | The gate process is the only owner of wheel motor handles. The proposer is a separate OS process with no actuator access and communicates over non-blocking localhost IPC. | Not a hardware safety PLC or STO relay. Separation is process-level on one host. Does not protect against gate process death; physical deployment requires hardware Safe Torque Off (STO) supervision. | **VERIFIED** | Test T-05 / Runs `RUN_1791713619` & `DEMO9_SCENARIO_B_FINAL`: Controller holds sole actuator handles; proposer isolated on UDP 5005. |
| C-2 Fail-closed command | The gate commands 0.0 rad/s on: proposer watchdog expiry, proposer disconnect, invalid lidar, range $\le d_{stop}$, or HSR critical/invalid telemetry. Issued within $\le 32\text{ ms}$. | Does not claim zero physical stopping distance. Physical stopping distance depends on inertia and traction. "Command issued" is not "robot stopped". | **VERIFIED** (Decomposed below) | Decomposed into verified sub-claims C-2a..C-2e below. |
| C-2a Obstacle stop | The gate commands 0.0 rad/s when minimum corridor range $\le d_{stop}$. Issued within 1 control tick ($32\text{ ms}$). | Stopping distance depends on deceleration envelope and ground traction. | **VERIFIED** | Run `RUN_1791713619`: Fired at $337\text{ mm}$ clearance; standstill reached at $301\text{ mm}$ ($36\text{ mm}$ coasting). Obstacle cart undisplaced at $X = 2.8\text{ m}$. |
| C-2b Watchdog expiry | The gate commands 0.0 rad/s when proposal age $\ge T_{watch}$ ($150\text{ ms}$). | Host scheduling jitter can trigger trips if proposer period is irregular under non-RTOS OS. | **VERIFIED** | Run `RUN_1791709882`: Watchdog trip observed and recorded at $t = 12.51\text{ s}$ when proposal age reached $128\,000\ \mu\text{s}$. Jitter mitigation confirmed in Demo 9 Take 2. |
| C-2c Proposer disconnect | The gate commands 0.0 rad/s when the proposer crashes or stops sending (`TRIP_PROPOSER_DEAD`). | Process restarts require monotonic `session_id` to resume without lockout (F3). | **VERIFIED** | Demo 8 sequencer take (`DEMO8_VIDEO_1792575455`) & unit tests in `test_gate_ipc.py`. |
| C-2d Invalid/stale lidar | The gate commands 0.0 rad/s on missing, NaN, blind, or stalled lidar data (`TRIP_SENSOR_INVALID`). | Sensor liveness relies on $\ge 5$ raw returns across 240° FOV. | **VERIFIED** | Tests in `test_gate_lidar.py` and Demo 8 fault injection sequence. |
| C-2e Distress reflex stop | The gate commands 0.0 rad/s on discrete cycle boundary ($\le 32\text{ ms}$) when HSR reports `CRITICAL` distress (`TRIP_HSR_CRITICAL`). | Distress confidence (0.85) is injected by test harness, not derived from a live computer vision pipeline. | **VERIFIED** | Demo 9 (`DEMO9_SCENARIO_B_FINAL`): Injected at $t = 4.000\text{ s}$ (Cycle 125); clamped to $0.000\text{ rad/s}$ with 0 added latency ticks (Invariant B3). |
| C-3 Tamper-evident log | Every gate evaluation is appended to a canonical JSONL log with rolling SHA-256 digests ($hash = \text{SHA256}(prev\_hash + canonical\_bytes)$). | Offline rewrite detectable only against an externally anchored head hash. Log records gate **commands**, not wheel ground truth. | **VERIFIED** | Demo 7 (`RUN_1791713619`, 1,485 records, seal `ae37...`) and Demo 9 (`DEMO9_SCENARIO_B_FINAL`, 438 records, seal `eccb0d85...`). Replay verified bit-for-bit via `verify_log.py --replay`. |
| C-4 IPC fault tolerance | The gate polls non-blocking, drains messages, caps datagram size, rejects NaN/Infinity, and steps reliably under proposer faults. | Windows 11 is not an RTOS. No hard real-time bound claimed. | **VERIFIED** | 12 unit tests in `test_gate_ipc.py` and `test_gate_link.py`. |
| C-5 Actuator fail-closed isolation | Actuator enforcement commands left and right wheels independently in isolated try-blocks (`zero_wheels`). Motor driver exceptions do not abandon the opposing wheel. | Does not replace physical brake coils or emergency stop relays. | **VERIFIED** | Unit tests in `tests/test_controller_actuators.py`: left and right motor faults simulated; opposing wheel successfully clamped to 0.0 rad/s. |
| C-6 Recovery contract | After a trip, the gate latches. Wheels stay at zero until: hazard is clear, continuous dwell elapses, and explicit operator reset arrives. Reset during hazard or while HSR is `MONITOR`/`CRITICAL` is strictly rejected (`RESET_REJECTED_HAZARD`). With `hsr_required=True`, reset is additionally refused (`RESET_REJECTED_NOT_READY`) until the Gate itself has observed $T_{dwell}$ of continuous fresh HSR `CLEAR` (see C-7b). | Does not replace a physical lockout/tagout (LOTO) procedure. | **VERIFIED** (hazard rejection, as evidenced); the added dwell clause is **IMPLEMENTED** (see C-7b) | Demo 9: Reset refused at $t = 5.024\text{ s}$ during distress (`RESET_REJECTED_HAZARD`); unit regression test in `test_gate_hsr.py` proves rejection when HSR is `MONITOR`. |
| C-7a Dual-dwell stabilization (direct `CRITICAL` to `CLEAR` path) | To prevent chattering and premature restart on transient clearance, recovery requires stacked dwell completion: HSR stabilizer dwell ($1.0\text{ s}$) followed by Gate clear dwell ($1.0\text{ s}$). | Availability cost: extends standstill recovery period by design; a single-sample sensor glitch causes a latched stop requiring full dwell and operator reset. Live evidence covers only the direct `CRITICAL` to `CLEAR` path: the harness injects only 0.85 distress or a hazard flag, so `MONITOR` is never produced live. | **VERIFIED** | Demo 9: Distress cleared at $t = 7.008\text{ s}$; HSR cleared at $t = 8.032\text{ s}$; Gate dwell completed at $t = 9.056\text{ s}$ before reset accepted (Invariants B4, B5). The Demo 9 log replays bit-for-bit through Gate v0.4 (438 cycles). |
| C-7b Gate-level HSR clear-dwell (all paths, including `MONITOR`) | With `hsr_required=True`, the Gate itself requires $T_{dwell}$ of continuous, fresh, valid HSR `CLEAR` readings (`hsr_clear_since_us`) both to enter `AWAITING_RESET` and to accept a reset, independent of any upstream stabilizer. `MONITOR`, `CRITICAL`, invalid, stale or future-stamped HSR, or a tick gap larger than `max_tick_gap_us`, restarts the run. A `MONITOR` blip after arming makes the Gate refuse reset (`RESET_REJECTED_NOT_READY`) until a fresh full run completes. Closes a defect in Gate v0.3, which counted `MONITOR` as calm and accepted a reset on a single `CLEAR` tick. | Enforced only when `hsr_required=True` (legacy mode unchanged). Not live-verified: evidenced by unit tests and an offline repro, not by a Webots run. Availability cost: on a path through `MONITOR`, recovery takes $\ge 1.0\text{ s}$ longer than under Gate v0.3 (repro: reset accepted $1.024\text{ s}$ after the first `CLEAR` tick, versus on the first `CLEAR` tick before). Does not validate the HSR classifier, and does not fix the upstream stabilizer, which measures elapsed time between samples rather than continuous observation (repro section E). | **IMPLEMENTED** | `tests/test_gate_hsr_clear_dwell.py` (8 tests; 5 of them fail on Gate v0.3); offline repro `qerra_gate_hsr.py`, sections C and D; Demo 9 log replay (see anchors note). |
| C-8 Proposer-channel poison recovery (2026-10-28 review finding F2) | The `(session_id, seq)` arbitration ratchet binds only while a live proposal (age $< T_{watch}$) is held. When none is held, a fresh (age $< T_{watch}$), valid, non-future candidate re-bases the ratchet. A single well-formed datagram with an astronomically large `session_id` or `seq` therefore blocks the legitimate proposer for at most the poisoned proposal's remaining freshness (repro: 4 rejected ticks, about $128\text{ ms}$, Gate in `RUN` afterwards) instead of permanently, as in Gate v0.3. Re-basing restores proposer liveness only: it does not lift a latch, shorten a dwell, or bypass operator reset. Stale, future-stamped and invalid datagrams never re-base. | Port 5005 is unauthenticated localhost UDP, and the sim-time echo that proposals copy is itself on localhost UDP (5007), so freshness is not authentication. A local sender that injects a higher `(session_id, seq)` on every tick still supplants the legitimate proposer (its proposals stay clamped to the envelope, AR-2, and subject to every trip). This is NOT defended against. Defence needs authenticated datagrams (for example a shared-key HMAC field) or OS-level channel isolation; neither is implemented. | **IMPLEMENTED** | `tests/test_gate_ratchet_rebase.py` (7 tests; 3 of them fail without the re-base); offline repro `qerra_gate_hsr.py`, section A. |

---

## 3. Definitions and parameters

| Symbol | Meaning | Value in Gate v0.4 |
|---|---|---|
| `dt` | Webots `basicTimeStep` | $32\text{ ms}$ ($32\,000\ \mu\text{s}$) |
| `T_watch` | Proposer freshness limit | $150\,000\ \mu\text{s}$ ($150\text{ ms}$, accommodating Windows thread jitter) |
| `T_stale` | Lidar freshness limit | $96\,000\ \mu\text{s}$ ($3 \times dt$) |
| `T_hsr_stale` | HSR heartbeat freshness limit | $96\,000\ \mu\text{s}$ ($3 \times dt$) |
| `T_dwell` | Continuous clear hysteresis before reset enabled (applied to the trip-cause dwell and, with `hsr_required=True`, independently to fresh HSR `CLEAR`, C-7b) | $1.0\text{ s}$ ($1\,000\,000\ \mu\text{s}$) |
| `w_max` | Maximum wheel angular velocity | $3.0\text{ rad/s}$ ($3\,000\,000\ \mu\text{rad/s}$) |
| `a_design` | Design deceleration envelope | $500\text{ mm/s}^2$ ($0.5\text{ m/s}^2$) |
| `margin` | Standstill clearance margin | $300\text{ mm}$ |
| `min_raw_lidar_returns` | Minimum finite raw returns for sensor liveness | $5$ across 240° raw scan |
| `t_react_us` | Reaction time allowance for stop envelope | $32\,000\ \mu\text{s}$ ($32\text{ ms}$, 1 tick) |
| `hsr_required` | Fail-closed enforcement of HSR reflex stream | `True` (trips `TRIP_HSR_INVALID` if missing/corrupt) |
| `d_stop(v)` | Mathematical stopping distance envelope | $\lceil v^2 / (2 \cdot a_{design}) \rceil + \lceil v \cdot t_{react} / 10^6 \rceil + margin$; at $2.0\text{ rad/s}$ ($0.196\text{ m/s}$) with $t_{react}=32\text{ ms}$, $d_{stop} = 346\text{ mm}$ |

---

## 4. Architecture rules

- **AR-1** The gate owns the wheel motors. No other process writes an actuator.
- **AR-2** The proposer can only propose speed reductions relative to the gate envelope, never exceed it.
- **AR-3** Gate envelope parameters are immutable at startup.
- **AR-4** Operator reset channel (UDP 5006 or edge-triggered keyboard) is isolated from proposer channel (UDP 5005).
- **AR-5** The gate never blocks on IPC (`recvfrom` non-blocking, bounded drain $\le 256$ datagrams/tick).
- **AR-6** IPC messages are capped at 2048 bytes, strictly parsed (no NaN/Inf), strictly typed integer values, with monotonic `session_id` arbitration (ratchet re-based only when no live proposal is held, C-8).
- **AR-7** Lidar scan ($667$ samples, $240^\circ$ FOV) is filtered through a $0.64\text{ m}$ swept corridor. Sensor liveness is judged on raw returns ($\ge 5$ returns across 240°) and pipeline freshness.
- **AR-8** Gate core is a pure function `step(state, params, inputs) -> StepResult` using strictly the Python standard library with zero external dependencies (verified via AST unit testing).
- **AR-9** Obstacle hazard classification is a direct deterministic stopping envelope check: `hazard = (min_range <= d_stop)`.
- **AR-10** HSR Reflex Integration Contract:
  - `CRITICAL` reflex state forces immediate transition to `Mode.TRIPPED` (`TRIP_HSR_CRITICAL`) and $0.0\text{ rad/s}$ command within $\le 32\text{ ms}$.
  - When `hsr_required=True`, missing, None, or unrecognized HSR statuses trip `TRIP_HSR_INVALID`.
  - Stale HSR heartbeat ($\text{age} > T_{hsr\_stale}$) trips `TRIP_HSR_STALE`.
  - In `Mode.AWAITING_RESET`, an operator reset is strictly rejected (`RESET_REJECTED_HAZARD`) unless HSR status is strictly `CLEAR`.
  - With `hsr_required=True`, the Gate requires its own $T_{dwell}$ of continuous fresh HSR `CLEAR` before entering `AWAITING_RESET` and before accepting a reset (`RESET_REJECTED_NOT_READY` otherwise), regardless of upstream stabilization (C-7b).
- **AR-11** Actuator Clamping Independence: `zero_wheels(left, right)` executes motor velocity clamping in separate isolated exception blocks to prevent asymmetric runaway if one actuator driver faults.
- **AR-12** ROS 2 Supervisory Gate Shell: `QerraGateNode` enforces sole write authority over `/cmd_vel_safe`. It discards mismatched lidar scans to fail closed (`TRIP_SENSOR_INVALID`), rejects contradictory HSR configurations at startup (`ValueError`), holds quiescent 0.0 m/s wheel commands on `RESET_ACCEPTED`, and ingests asynchronous reflex telemetry non-blocking via `HsrReceiver` (UDP port 5008).

---

## 5. Audit Log Specification (Schema Version 1)

Every evaluation writes one canonical JSON line to `results/<run_id>/gate_audit.jsonl` using binary LF (`\n`):

| Field | Type | Description |
|---|---|---|
| `v` | int | Schema version (`1`) |
| `run_id` | string | Unique run identifier |
| `seq` | int | Strictly monotonic sequence number ($0, 1, 2, \dots$) |
| `sim_time_us` | int | Integer microseconds of Webots simulation time |
| `wall_ns` | int | Host `perf_counter_ns` timestamp |
| `state` | string | `RUN`, `TRIPPED`, `AWAITING_RESET` |
| `reason` | string | Primary decision reason (`PASS`, `TRIP_OBSTACLE`, `TRIP_PROPOSER_DEAD`, `TRIP_PROPOSER_STALE`, `TRIP_SENSOR_INVALID`, `TRIP_HSR_CRITICAL`, `TRIP_HSR_INVALID`, `TRIP_HSR_STALE`, `TRIP_LOG_FAILURE`, `TRIP_CLOCK_ANOMALY`, `LATCHED_DWELL`, `LATCHED_AWAIT_RESET`, `RESET_ACCEPTED`) |
| `events` | list[str] | Secondary events (`RESET_REJECTED_HAZARD`, `RESET_REJECTED_CHANNEL`, `RESET_REJECTED_NOT_READY`, `MSG_REJECTED_*`, etc.) |
| `proposal_seq` | int or null | Sequence number of active proposal |
| `proposal_age_us` | int or null | Proposal age in sim microseconds ($\text{sim\_now} - \text{sim\_stamp}$) |
| `lidar_valid` | bool | Scan integrity flag |
| `lidar_min_mm` | int or null | Minimum corridor obstacle distance |
| `d_stop_mm` | int | Commanded stopping distance envelope ($\lceil v^2 / 2a \rceil + \lceil v \cdot t_{react} / 10^6 \rceil + margin$) |
| `obstacle_breach` | bool | Direct stopping envelope breach flag (`True` if `lidar_min_mm <= d_stop_mm`) |
| `hsr_status` | string or null | Live assistive reflex telemetry (`CLEAR`, `MONITOR`, `CRITICAL`, or `null`) |
| `hsr_age_us` | int or null | Age of HSR evaluation in microseconds ($\text{sim\_now} - \text{hsr\_stamp}$) |
| `cmd_left_urad_s` | int | Output command to left wheel ($\mu\text{rad/s}$) |
| `cmd_right_urad_s` | int | Output command to right wheel ($\mu\text{rad/s}$) |
| `inputs` | dict (optional) | Serialized tick inputs enabling exact offline replay of `step()` |
| `manifest` | dict (optional) | Sealed in record 0 (`seq=0`): run ID, gate version, parameters, and harness fault injection switches |
| `gate_version` | string | Controller software release (`0.4` from this release; the Demo 7 and Demo 9 anchors carry `0.2` and `0.3`) |
| `prev_hash` | string | Hex SHA-256 of preceding log entry (Genesis: 64 zeros) |
| `hash` | string | `SHA256(prev_hash_ascii || canonical_bytes)` |

`hsr_clear_since_us` (C-7b) is Gate internal state and is not a logged field. `verify_log.py --replay` reconstructs it from the logged `hsr_status` and `hsr_stamp_us` inputs.

---

## 6. Revision log

| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-10-10 | Initial specification. All items SPECIFIED. |
| 0.2 | 2026-10-12 | Evidenced run `RUN_1791713619` attached. Claims C-1, C-2, C-3, C-4, C-6 raised to VERIFIED. Parameter defaults synchronized to $150\text{ ms}$ and $500\text{ mm/s}^2$. |
| 0.3 | 2026-10-17 | Hardened supervisory gate under independent review findings: F1-F8. Added reaction time allowance $t_{react}$ in $d_{stop}$ ($346\text{ mm}$ envelope). |
| 0.4 | 2026-10-18 | Epistemic truth alignment under findings V1-V11: landed real F3 IPC unit tests (103 gate tests); verified deterministic offline replay via `verify_log.py --replay`; documented V5 simulated-only stale watchdog and V6 forward-arc occlusion boundaries. |
| 0.5 | 2026-10-27 | Integrated Layer 1B QERRA-HSR reflex companion under Demo 9 (`DEMO9_SCENARIO_B_FINAL`, 438 cycles, Head Seal `eccb0d85...`). Added Claim C-2e (Distress reflex stop $\le 32\text{ ms}$) and Claim C-7 (Dual-dwell stabilization against chattering). Hardened Claim C-6 recovery contract to strictly reject reset in `AWAITING_RESET` when HSR is non-clear (`MONITOR`/`CRITICAL`). Documented independent actuator clamping (AR-11, C-5), host scheduling jitter diagnostics, active `hsr_status` and `hsr_age_us` log fields, and bumped Gate unit tests to 113. |
| 0.6 | 2026-10-29 | Gate/HSR boundary review of 2026-10-28 (findings F1 dwell, F2 ratchet; numbering distinct from the v0.3 findings F1-F8). Split Claim C-7 into C-7a (VERIFIED, direct `CRITICAL` to `CLEAR` path, Demo 9) and C-7b (IMPLEMENTED, Gate-level continuous HSR `CLEAR` dwell via `hsr_clear_since_us`; closes the defect where the Gate counted `MONITOR` as calm and accepted reset on a single `CLEAR` tick; about $1.0\text{ s}$ added availability cost on the `MONITOR` path; not live-verified). Added Claim C-8 (ratchet re-basing, IMPLEMENTED) with explicit non-claim: unauthenticated localhost UDP, hostile local sender not defended against. Amended C-6, AR-6, AR-10, parameters and audit-log notes. Gate core bumped to v0.4. Gate unit tests: 130 (`test_gate_*.py`: 115 existing + 8 C-7b + 7 C-8), plus 3 actuator tests. Demo 9 log (438 cycles) replays bit-for-bit through v0.4. |
| 0.7 | 2026-10-30 | **ROS 2 Integration & Clock Hardening:** Packaged Gate v0.4 into a standalone ROS 2 Jazzy node (`qerra_gate_node`). Addressed two safety hazards identified in node review: (1) Unified clock domain (`use_sim_time` compatible) to prevent negative-age watchdog faults caused by mixing OS wall time and ROS message epochs. (2) Replaced dynamic `GateParams` auto-configuration with fixed startup parameters (`lidar_n_expected=682`, `lidar_fov_rad=240°`) to prevent silent geometric reconfiguration from a damaged sensor array, restoring strict length-integrity validation (fail-closed `TRIP_SENSOR_INVALID`). |
| 0.8 | 2026-10-31 | **ROS 2 Layer 1B Telemetry & Fail-Closed Hardening:** Wired `HsrReceiver` into `qerra_gate_node` via UDP port 5008 (worst-severity batch reduction per 32 ms tick). Added simulation clock echo on UDP port 5007 (`gate_link.send_state()`) to sync external perception producers (`synthetic_hsr_producer.py`). Enforced fail-closed scan discard on beam count mismatch to prevent subscriber callback termination. Added startup configuration guard rejecting `hsr_source="none"` when `hsr_required=True`. Verified quiescent re-arm tick holding 0.0 m/s on `RESET_ACCEPTED`. |
