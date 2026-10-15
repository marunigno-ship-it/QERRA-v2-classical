<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<!-- Copyright (c) 2026 Marussa Metocharaki -->

# QERRA Supervisory Gate (Demo 7) — Safety Concept

| | |
|---|---|
| Document version | 0.3 (Decoupled pure stdlib core, verified against RUN_1791713619) |
| Date | 2026-10-15 |
| Author | Marussa Metocharaki |
| System under demonstration | QERRA Supervisory Gate, simulated PAL Robotics TIAGo in Webots R2025a, Windows 11 |
| Status vocabulary | **SPECIFIED** (written, nothing built) → **IMPLEMENTED** (code exists, not yet evidenced) → **VERIFIED** (test passed; evidence = test ID + commit hash / Run ID + log head hash) |

**Evidence Anchor for v0.2:**
* **Run ID:** `RUN_1791713619`
* **Verified Records:** 1,485 continuous ticks ($t = 0.032\text{ s}$ to $t = 47.520\text{ s}$)
* **Cryptographic Head Seal:** `ae37ae62227c4fdca51233b7e4189607898ae2c27eca5bf0847414d1f0d4c191`
* **Anchor File:** `results/RUN_1791713619/ANCHOR.txt`

---

## 1. Purpose and scope

Demo 7 demonstrates one architectural property: **authority separation**:

> Deliberation is an untrusted proposer. It may be late, wrong, or dead. The supervisory gate is the only path to the wheels. The default is stop.

In scope: a gate process that owns the wheel motors, an untrusted proposer process, a lidar-derived stop rule, a latched stop with explicit operator reset, a tamper-evident decision log, and a fault-injection test plan.

Out of scope for Demo 7: moral filtering (SEMEV-12), values ranking (THRIVE), perception, navigation, manipulation, payload dynamics, hardware safety functions, certification. The moral and values layers are deliberate non-claims for this document.

This is a research prototype in simulation. It is not a certified safety function and not a commercial product.

Informative references (names only; clause numbers omitted until checked against purchased standards): ISO 12100 (risk assessment), ISO 13849-1, IEC 62061, IEC 61508, ISO 10218-1/-2, ISO 13482, ISO 3691-4.

---

## 2. Claims and non-claims

| ID | Claim (what Demo 7 evidences) | Non-claim (explicit boundary) | Status | Evidence |
|---|---|---|---|---|
| C-1 Authority separation | The gate process is the only owner of the wheel motor handles. The proposer is a separate OS process with no actuator access and communicates over non-blocking localhost IPC. | Not a hardware safety PLC or STO relay. Separation is process-level on one non-real-time host. Does not protect against gate process death (H-07). | **VERIFIED** | Test T-05 / Run `RUN_1791713619`: Webots simulation controller runs with sole actuator handles; external proposer PID 4140 isolated on UDP 5005. (Smoke-test baseline: obstacle placed via supervisor script at $t = 3.5\text{ s}$; decoupled supervisor robot scheduled next). |
| C-2 Fail-closed command | The gate commands 0.0 rad/s on: proposer watchdog expiry, proposer disconnect, invalid lidar data, or range $\le d_{stop}$. Issued within one control tick ($32\text{ ms}$). | Does not claim zero stopping distance. Physical stopping distance depends on simulated traction. "Command issued" is not "robot stopped". | **VERIFIED** | Tests T-01, T-02, T-11 / Run `RUN_1791713619` (Head seal `ae37...c191`): commanded $0.0\text{ rad/s}$ within 1 tick ($32\text{ ms}$). Dynamic envelope $d_{stop} = 339\text{ mm}$; trip command fired at $337\text{ mm}$ clearance; physical standstill reached at $301\text{ mm}$ minimum clearance ($36\text{ mm}$ coasting). Obstacle cart undisplaced at $X = 2.8\text{ m}$. |
| C-3 Tamper-evident log | Every gate evaluation is appended to a JSONL log with canonical serialization and a SHA-256 hash chain, with monotonic sequence number and sim time. | Offline rewrite is detectable only against an externally anchored head hash. The log records gate **commands**, not wheel ground truth. | **VERIFIED** | Test T-13 / Run `RUN_1791713619`: 1,485 records verified with 0 defects by `verify_log.py`. Head hash `ae37ae62...c191` anchored in `ANCHOR.txt`. |
| C-4 IPC fault tolerance | The gate polls non-blocking, drains messages, caps datagram size, rejects NaN/Infinity, and continues stepping if the proposer stalls or dies. | Windows 11 is not an RTOS. No hard real-time bound claimed. Not hardened against malicious local processes. | **VERIFIED** | Tests T-04, T-06, T-09: 7 unit tests pass in `test_gate_ipc.py` (plus `test_gate_link.py`). NaN/Inf parse callback tested; datagram buffer capped at 2048 bytes; drain loop bounded to 256 datagrams/tick. |
| C-5 Counterfactual evidence | Scenarios evaluate outcomes (minimum clearance, collision, blind travel distance) with deterministic reporting. | Run A is a lower-bound baseline, not a representative commercial controller. No ISO 13849-1 PL or IEC 62061 SIL claim. | **IMPLEMENTED** | Counterfactual test framework specified. |
| C-6 Recovery contract | After a trip the gate latches. Wheels stay at zero until hazard is clear, continuous $1.0\text{ s}$ dwell elapses, and explicit operator reset arrives. Reset during hazard is rejected. | Does not replace a physical emergency stop or lockout/tagout. | **VERIFIED** | Tests T-10, T-11 / Run `RUN_1791713619`: `RESET_REJECTED_HAZARD` verified empirically at $t = 34\text{ s}$ when operator reset attempted facing the obstacle cart (events: `['RESET_REJECTED_HAZARD']`). |
| C-7 Fail-closed availability cost | The robot stops whenever the proposer is late, whether or not a hazard exists. | Does not claim the stop policy is optimal for throughput. | **VERIFIED** | Test T-03 / Run `RUN_1791709882`: Watchdog trip observed and recorded at $t = 12.51\text{ s}$ when proposal age reached $128\,000\ \mu\text{s}$ (exceeding initial $100\text{ ms}$ threshold). Freshness limit adjusted to $150\text{ ms}$ for Windows scheduling jitter tolerance. |

---

## 3. Definitions and parameters

| Symbol | Meaning | Value in Demo 7 |
|---|---|---|
| `dt` | Webots `basicTimeStep` | $32\text{ ms}$ ($32\,000\ \mu\text{s}$) |
| `T_watch` | Proposer freshness limit | $150\,000\ \mu\text{s}$ ($150\text{ ms}$, accommodating Windows thread jitter) |
| `T_stale` | Lidar freshness limit | $96\,000\ \mu\text{s}$ ($3 \times dt$) |
| `T_dwell` | Continuous clear hysteresis before reset enabled | $1.0\text{ s}$ ($1\,000\,000\ \mu\text{s}$) |
| `w_max` | Maximum wheel angular velocity | $3.0\text{ rad/s}$ ($3\,000\,000\ \mu\text{rad/s}$) |
| `a_design` | Design deceleration envelope | $500\text{ mm/s}^2$ ($0.5\text{ m/s}^2$) |
| `margin` | Standstill clearance margin | $300\text{ mm}$ |
| `d_stop(v)` | Stop distance envelope | $\lceil v^2 / (2 \cdot a_{design}) \rceil + margin$; at $2.0\text{ rad/s}$ ($0.196\text{ m/s}$), $d_{stop} = 339\text{ mm}$ |

**Observed Proposal Freshness:** Min $32\,000\ \mu\text{s}$, Max $64\,000\ \mu\text{s}$ during steady state execution (`RUN_1791713619`).

**Note on High-Speed Stop Envelopes:**  
At cruise speed $0.196\text{ m/s}$, the kinematic braking term is $\sim 39\text{ mm}$, so the $300\text{ mm}$ margin dominates and comfortably absorbs tick reaction latency ($32\text{ ms}$) and proposer delay. At higher velocities ($\ge 1.0\text{ m/s}$), an explicit reaction-time term $v \cdot (dt + T_{watch})$ must be added to $d_{stop}$ before physical calibration T-12.

---

## 4. Architecture rules

- **AR-1** The gate owns the wheel motors. No other process writes an actuator.
- **AR-2** The proposer can only propose speed reductions relative to the gate envelope, never exceed it.
- **AR-3** Gate envelope parameters are immutable at startup.
- **AR-4** Operator reset channel (UDP 5006 or edge-triggered keyboard) is isolated from proposer channel (UDP 5005).
- **AR-5** The gate never blocks on IPC (`recvfrom` non-blocking, bounded drain $\le 256$ datagrams/tick).
- **AR-6** IPC messages are capped at 2048 bytes, strictly parsed (no NaN/Inf), strictly typed integer values.
- **AR-7** Lidar scan ($667$ samples, $240^\circ$ FOV) is filtered through a $0.64\text{ m}$ swept corridor. Invalid data causes an immediate trip.
- **AR-8** Gate core is a pure function `step(state, params, inputs) -> StepResult` using strictly the Python standard library with zero external dependencies (verified via AST unit testing).
- **AR-9** Obstacle hazard classification is a direct deterministic stopping envelope check: `hazard = (min_range <= d_stop)`. It is decoupled from high-level or assistive reflex layers (`hsr/`).

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
| `reason` | string | Primary decision reason (`PASS`, `TRIP_OBSTACLE`, `TRIP_PROPOSER_DEAD`, `TRIP_PROPOSER_STALE`, `TRIP_SENSOR_INVALID`, `TRIP_LOG_FAILURE`, `TRIP_CLOCK_ANOMALY`, `LATCHED_DWELL`, `LATCHED_AWAIT_RESET`, `RESET_ACCEPTED`) |
| `events` | list[str] | Secondary events (`RESET_REJECTED_HAZARD`, `RESET_REJECTED_CHANNEL`, `MSG_REJECTED_*`, etc.) |
| `proposal_seq` | int or null | Sequence number of active proposal |
| `proposal_age_us` | int or null | Proposal age in sim microseconds ($\text{sim\_now} - \text{sim\_stamp}$) |
| `lidar_valid` | bool | Scan integrity flag |
| `lidar_min_mm` | int or null | Minimum corridor obstacle distance |
| `d_stop_mm` | int | Commanded stopping distance envelope |
| `obstacle_breach` | bool | Direct stopping envelope breach flag (`True` if `lidar_min_mm <= d_stop_mm`) |
| `hsr_status` | string or null | Decoupled in v0.3 (`null`); reserved for external assistive reflex telemetry |
| `cmd_left_urad_s` | int | Output command to left wheel ($\mu\text{rad/s}$) |
| `cmd_right_urad_s` | int | Output command to right wheel ($\mu\text{rad/s}$) |
| `gate_version` | string | Controller software release |
| `prev_hash` | string | Hex SHA-256 of preceding log entry (Genesis: 64 zeros) |
| `hash` | string | `SHA256(prev_hash_ascii || canonical_bytes)` |

---

## 6. Revision log

| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-10-10 | Initial specification. All items SPECIFIED. |
| 0.2 | 2026-10-12 | Evidenced run `RUN_1791713619` attached. Claims C-1, C-2, C-3, C-4, C-6 raised to VERIFIED with exact test IDs and hash seals. Claim C-2 refined to report $337\text{ mm}$ trip vs $301\text{ mm}$ physical standstill ($36\text{ mm}$ coasting). High-speed reaction time term documented. Parameter defaults synchronized to $150\text{ ms}$ and $500\text{ mm/s}^2$. |
| 0.3 | 2026-10-15 | Decoupled `hsr/` from `gate_core.py`. Enforced AR-8 (pure standard library, AST verified in test suite). Updated AR-9 to direct deterministic envelope check (`min_mm <= stop_mm`). Added `obstacle_breach` to record schema. All 75 gate unit tests verified passing. |
