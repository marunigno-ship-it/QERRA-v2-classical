# Simulation Demo 10: Asynchronous HSR Telemetry Integrity, Frozen-Frame Fault & Controlled Recovery

**Run ID:** `DEMO10_FROZEN_FRAME_20261120_125540`  
**Simulator:** Webots R2025a (PAL Robotics TIAGo base) on Windows 11  
**World:** `worlds/demo10_hsr_integrity.wbt`  
**Controller:** `controllers/tiago_supervisory_gate/tiago_supervisory_gate.py` (`--demo10-frozen-frame`)  
**Gate Core Version:** `v0.4`  

---

## 1. Objective & Architectural Fix Verified

Demo 10 validates the **asynchronous UDP HSR telemetry path** and closes an earlier divergence between ROS 2 and Webots:
* Previously, the Webots UDP adapter only performed worst-severity batch reduction and discarded observation sequence IDs (`obs_id`), making frozen camera/perception frames invisible when timestamps continued advancing.
* Both ROS 2 (`ros2/hsr_receiver.py` shim) and Webots now share a single pure-Python receiver (`gate/hsr_receiver.py`) backed by `step_hsr_stream()` in `gate/hsr_telemetry.py`.
* The external synthetic producer (`scripts/synthetic_hsr_producer.py`) operates as an independent, event-driven OS process synchronized via dedicated UDP clock channel port `5009` (isolated from the proposer clock channel on port `5007`), transmitting HSR telemetry packets over UDP port `5008`.

---

## 2. Recorded Simulation Configuration (from `manifest.json`)

| Parameter | Value |
| :--- | :--- |
| `QERRA_HSR_SOURCE` | `udp` (Port `5008`, State Clock Port `5009`) |
| `QERRA_HSR_MODE` | `frozen_frame` (`4.0 s` to `7.0 s` simulated window) |
| `hsr_required` | `true` |
| `t_hsr_stale_us` | `96,000 µs` (`96 ms`) |
| `t_dwell_us` | `1,000,000 µs` (`1.0 s`) |
| `dt_us` | `32,000 µs` (`32 ms`) |
| `lidar_n_expected` | `667` samples (`240°` FOV, `0.64 m` corridor width) |
| `reset_origin` | `automated_test_harness` (`1.2 s`, `5.0 s`, `8.3 s`) |

---

## 3. Observed Timeline (`DEMO10_FROZEN_FRAME_20261120_125540`)

| Sim Time | Event | Gate / HSR State | Command Output |
| :--- | :--- | :--- | :--- |
| `0.03 s` | Startup prior to UDP stream lock | `START -> TRIPPED` (`TRIP_HSR_INVALID`) | `0.000 rad/s` |
| `0.224 s` | Event-driven UDP HSR producer online | `[HSR] None -> CLEAR` | `0.000 rad/s` |
| `1.216 s` | Startup reset prior to 1.0 s dwell | `RESET_REJECTED_NOT_READY` | `0.000 rad/s` |
| `1.248 s` | Startup dwell complete, reset accepted | `TRIPPED -> RUN` (`RESET_ACCEPTED`) | Cruises at `2.00 rad/s` |
| `4.032 s` | **Frozen frame injected** (`obs_id` static, timestamps advance) | `[HSR] CLEAR -> None`, **`RUN -> TRIPPED` (`TRIP_HSR_INVALID`)** (LiDAR `3820 mm`, Proposer age `32 ms`) | **`0.000 rad/s` (fail-closed)** |
| `5.024 s` | Automated reset attempted during active freeze | **`RESET_REJECTED_HAZARD`** (holds `TRIPPED`) | `0.000 rad/s` |
| `7.200 s` | Advancing frames resume at `7.0 s`; dual-gate rebase (5 ticks + `160 ms`) completes | `[HSR] None -> CLEAR` | `0.000 rad/s` |
| `8.22 s` | Gate `1.0 s` calm dwell completes | **`TRIPPED -> AWAITING_RESET`** (`Calmed. Awaiting scripted reset request.`) | `0.000 rad/s` |
| `8.320 s` | Scripted recovery reset accepted | `AWAITING_RESET -> RUN` (`RESET_ACCEPTED`) | Stationary on reset tick (`0.000 rad/s`); resumes `2.00 rad/s` next tick |
| `14.05 s` | `QERRA_END_AT_S` (`14.02 s`) reached | Clean exit, logs & CSV closed | `0.000 rad/s` |

---

## 4. Measured Execution Timing & Cryptographic Replay Verification

* **Per-tick Gate Compute Latency (`N = 439`):** `p50 = 1068.7 µs` | `p99 = 2774.6 µs` | `max = 2990.1 µs`
* **Host Iteration Wall Intervals (`N = 438`):** `p50 = 32.0 ms` | `p99 = 53.0 ms` | `max = 148.3 ms`
* **Replay Verification (`verify_log.py --replay`):**
  * Verified Records: **`439 / 439`** (`Sequence 0 -> 438`)
  * Result: **`[REPLAY AUDIT PASSED]`** bit-for-bit through pure `gate_core.step()`
  * Head Hash (SHA-256 Seal): `0250fdcbff64af691dc52f5d60a89305d691ce3ca6b662281e7e9c73ff46437a`
  * Anchor Status: `UNANCHORED` (local unanchored log)
* **Host Test Suite (`python -m pytest`):** `270 passed, 14 skipped` (ROS 2 container tests skipped on Windows host), `0 failures` (including `tests/test_demo10_stream_recovery.py`).

### Recorded SHA-256 Code Hashes (`manifest.json`)
* `controller`: `86582f45b3219cc6e190ae1d73af48d8243775b0448cb02381eddd9ad2835f54`
* `gate_core`: `5af925355e636e42743093f35e0fcbd063a7299f0802310abf22eeb8fc9e5b9e`
* `gate_ipc`: `8271f32cbc605ba3f70393c15ab8f7faf6fc5c0cff972804ac0e62c47fb09198`
* `gate_lidar`: `858a0efb98ddd67410d6ddeb01b49167648b83cb7dbe4ed77e1751b392b2f086`
* `gate_log`: `375710dece5f278eef4cd3b892c42094f183869d202ad83564cf7ee7f384c0a8`
* `hsr_producer`: `761c8b1d115790ad7c0d709dd61668a7148d8f6e9ad11a4fc42cb781076a1df2`
* `hsr_receiver`: `a6b8d2698ccd496a6c121c44714f37d14fe9943086e73c9eb1a93c48ec301d3e`
* `hsr_telemetry`: `4f0b2d403ba728756ed44f0ab8967b971c8aa9e1af2d3b32cf7a696c0a66615c`
* `proposer`: `a13444c9142134c0a9e487bd14a35b7bf17addf02429a196241900f20ad5b958`
* `verify_log`: `3136386d01580851711455aaa1e4cade28578f35967336f5c85b7057e059c503`

---

## 5. Disclosures & Scope Boundaries

* **Synthetic HSR Inputs:** All HSR signals in this demonstration are generated synthetically by `scripts/synthetic_hsr_producer.py`. No live camera perception or human-subject distress inference is performed.
* **Simulation Only:** Executed in Webots R2025a on Windows 11 (non-RTOS desktop host). This is not physical robot hardware validation or safety certification.
* **Software Setpoint vs. Hardware Stop:** A `0.000 rad/s` velocity output is a software setpoint command, not an ISO 13849-1 Safe Torque Off (STO) or mechanical brake.
* **Automated Harness Resets:** Reset requests at `1.2 s`, `5.0 s`, and `8.3 s` were injected by the scripted test harness (`automated_test_harness`) for deterministic reproducibility, not by a physical operator pressing a button.
