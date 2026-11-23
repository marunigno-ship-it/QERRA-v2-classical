<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright (c) 2026 Marussa Metocharaki -->

# QERRA-v2 Classical: Supervisory Gate and Reflex Layer for ROS 2 Jazzy

## Executive Architectural Reference (frozen)

**Author:** Marussa Metocharaki, independent developer  
**Software baseline:** Release v2.4.2+ on `main`  
**Platform:** ROS 2 Jazzy, Ubuntu 24.04 Noble; simulation in Webots R2025a (PAL Robotics TIAGo base model)  
**Repository:** <https://github.com/marunigno-ship-it/QERRA-v2-classical>  
**Status of this file:** frozen permalink. It describes the architecture and its boundaries. It contains no test counts, commit hashes or run numbers. Current details live in the files listed in section 7.

---

## 1. What this is, and what it is not

QERRA-v2 Classical is an open-source **simulation research prototype**. Layer 1A is a deterministic supervisory gate between an untrusted velocity proposer (planner, teleoperation, learned policy) and a mobile base controller. Layer 1B is a reflex-telemetry input to that gate. SEMEV-12 and QERRA-THRIVE are advisory deliberation layers outside this document and outside the physical safety function.

- No physical AMR hardware has been tested. Evidence consists of Webots simulation runs, unit tests, and ROS 2 integration tests in a `ros:jazzy` container in CI.
- No functional-safety certification, Performance Level, Safety Integrity Level or standards conformity is claimed. ISO 13849-1, ISO 13482, ISO 3691-4 and EN 50159 are informative design references only.
- A `(0, 0)` software velocity command is a setpoint. It is not a certified emergency stop, a mechanical brake, or a hardware Safe Torque Off (STO).

## 2. Architecture

```text
 planner / teleop / policy        (untrusted proposer)
          │  /cmd_vel   (remappable)
          ▼
 ┌─────────────────────── qerra_gate_node (qerra_core) ───────────────────────┐
 │  /scan   /odom   HSR telemetry   /gate/reset                               │
 │        └──────────────► Gate Core: step(state, params, inputs) ────────────┼──► /cmd_vel_safe ──► base controller
 └─────────────────────────────────────────────────────────────────────────────┘      (own braking, own command watchdog)
```

**Doer-Checker separation.** The Gate is strictly a Checker. On any trip it commands wheel setpoints `(0, 0)` immediately. Generating a deceleration profile (`TRIP_BRAKING`) inside the Gate was evaluated and rejected: a supervisor that plans motion after a trip is no longer a checker, and it would own a motion profile it cannot verify against the real drive. Physical braking belongs to the base controller.

## 3. Layer 1A: Supervisory Gate

- **Implementation:** `gate/gate_core.py`, one pure function, `step(state, params, inputs) -> StepResult`. Python standard library only: no numpy, no ROS, no external math. An AST-based test enforces this. No file, socket or clock access; time is an explicit input.
- **Units:** integers throughout: microseconds, micro-radians per second (`urad/s`), millimetres.
- **Dynamic stopping envelope**, in integer millimetres:

  ```text
  d_stop = ceil(v_ref² / (2·a)) + ceil(v_ref · t_react / 10⁶) + margin
  a = 500 mm/s²      margin = 300 mm      v_ref in mm/s      t_react in µs
  v_ref = max(v_cmd, v_meas_x)
  ```

  `v_cmd` is the commanded wheel speed after clamping. `v_meas_x` is the forward translational speed derived from wheel feedback; pure in-place yaw spin contributes none. An obstacle in the forward corridor at or inside `d_stop` trips the gate.
- **Reverse clamping:** with `w_min = 0`, a negative wheel request on either wheel sets both wheel commands to `(0, 0)`.
- **Trips (fail-closed):** obstacle inside `d_stop`, invalid or stale lidar, stale or missing proposer, non-monotonic clock, HSR critical/invalid/stale (when HSR is required), log-write failure. The initial state is `TRIPPED`.
- **Recovery:** latched. It needs a continuous 1.0 s clear dwell, valid HSR `CLEAR` for its own dwell when HSR is required, and an explicit `operator` reset. The reset tick itself outputs `(0, 0)`.
- **Standstill-qualified dwell.** This resolves the "Standstill Dwell Trap": a calm dwell that elapses while the platform is still coasting. With `standstill_required=True`, the 1.0 s dwell in `Mode.TRIPPED` starts only after measured wheel feedback shows both wheels within 50,000 µrad/s (0.05 rad/s) of zero, and it restarts from zero if motion resumes. Missing feedback blocks the dwell.
- **Non-finite proposal inhibition:** a `NaN` or `Inf` velocity proposal commands `(0, 0)` in `Mode.RUN` and does not refresh the proposer watchdog. If valid proposals do not resume, the existing 150 ms watchdog escalates to `TRIP_PROPOSER_STALE`.

## 4. Layer 1B: QERRA-HSR reflex input

HSR supplies a `CLEAR` / `MONITOR` / `CRITICAL` status over a UDP telemetry contract. The gate uses it as follows:

- `CRITICAL` trips the gate. `MONITOR` imposes no speed cap in `RUN`; it only blocks recovery while the gate is latched.
- A stream monitor checks **arrival-order packet sequence integrity** before any reduction of the batch. A repeated `obs_id` latches a **sticky freeze**, and the receiver then presents no valid status.
- A counter regression (producer restart) trips fail-closed and starts a **dual-gate rebase dwell**: at least 5 control ticks **and** at least 160 ms of observed time. Only then are fresh frames accepted again. The gate's own 1.0 s dwell and operator reset still apply.
- The stream monitor and receiver are pure Python. The monitor detects counter faults. It cannot detect a frozen sensor behind a producer that keeps publishing fresh counters and timestamps.
- Thresholds are author-chosen placeholders. The wire packet carries no metric person distance. All demonstration input is injected or synthetic, and no perception performance is claimed.

## 5. ROS 2 node adapter

- **Package:** `qerra_core` (`ament_python`), node `qerra_gate_node`. Topic remappings (Pattern B) and typed parameters are exposed through `launch/qerra_gate.launch.py`.
- **`/odom` ingestion:** the measured twist is converted to integer wheel speeds. A 100 ms freshness watchdog, including a check for backward clock jumps, discards stale input, and discarded feedback blocks the standstill-qualified dwell.
- **`NodeFaultLatch`:** an unhandled exception in the control tick latches a process-lifetime fault. The node publishes zero every tick, reports `FAULT`, and only a process restart clears it.
- **Flight log (optional):** a rolling SHA-256 hash chain of every gate decision. `verify_log.py --replay` recomputes the recorded decisions bit-for-bit offline. A write failure trips the gate on the same tick. The chain is tamper-evident only against a head hash stored elsewhere.
- **Reaction-time budgets:** 96 ms (ROS 2 simulation profile) and 160 ms (10 Hz scanner profile) are engineering estimates of the signal chain. They are not measured values and not real-time bounds.

## 6. Boundaries

- **Authority is conventional.** ROS 2 does not enforce a sole publisher. The base controller must be configured to accept commands only from the gate output. Any process that can publish to the base command topic bypasses the gate.
- **Localhost and ROS topics are unauthenticated.** Defense against a compromised local process (forged HSR telemetry, forged reset, forged `/odom`) belongs to OS permissions and DDS/SROS2, not to this node. Executable tests demonstrate two such attacks the design does not stop.
- **Timing is not guaranteed.** The node runs in Python on a general-purpose OS. No worst-case execution time has been measured.
- **Odometry validity.** `/odom` confirms standstill only if it comes from closed-loop wheel feedback (`open_loop=false` in `diff_drive_controller`). Under open-loop odometry or locked-wheel skidding it does not.
- **Stopping physics.** The design deceleration (500 mm/s²) and the 300 mm margin are not validated on hardware.
- **At the time of writing:** obstacle geometry is one forward corridor, not a swept footprint for turns, and `LaserScan` metadata beyond beam count is not validated. Check `LIMITATIONS.md` for the current state.

## 7. Canonical pointers

This file will not be updated. For anything current, use these:

- [`README.md`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/README.md): build instructions, launch parameters, latest verified test metrics.
- [`SAFETY_CONCEPT.md`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/SAFETY_CONCEPT.md): formal specification, invariants, Claims C-1 to C-7.
- [`LIMITATIONS.md`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/LIMITATIONS.md): real-world boundaries and non-claims.
