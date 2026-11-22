<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright (c) 2026 Marussa Metocharaki -->

# QERRA-v2 Classical: ROS 2 Jazzy Supervisory Gate and Assistive Reflex

## Technical Brief: Deterministic Kinematic Supervision, Reflex Telemetry, and Node-Level Fault Handling

**Author:** Marussa Metocharaki, Independent Researcher and Developer  
**Target audience:** Autonomous Mobile Robot (AMR) Systems Engineers, Functional Safety Researchers, and Verification Specialists  
**Date:** 22 November 2026  
**Document version:** 1.7.0  
**Software baseline:** Package metadata updated to Release v2.4.2 on `main` (verified at commit `5734dd7` prior to documentation sync), incorporating Gate Core v0.5 standstill-qualified recovery dwell and ROS 2 `/odom` measured-feedback integration, Phase 1 non-finite Twist command inhibition and flight-log replay support, and Milestones 2.1 and 2.2 (Layer 1B wire-contract v0.4.0 mandatory-field hardening and HSR receiver rejection diagnostics); standalone `qerra_core` (`ament_python`, `package.xml` format 3, Apache-2.0, declaring `<exec_depend>nav_msgs</exec_depend>` alongside `launch` and `launch_ros`); ROS 2 node `qerra_gate_node` v0.3.1; pure-function Gate Core v0.5 (`gate/gate_core.py`); HSR telemetry contract `gate/hsr_telemetry.py` v0.4.0; `src/qerra_msgs` masked by `src/qerra_msgs/COLCON_IGNORE` and excluded from package discovery, build and `package.xml` dependencies; installed launch entry point `launch/qerra_gate.launch.py` exposing 15 typed parameters and 6 topic remappings (21 launch arguments in total); flight-log schema v1 (`gate/gate_log.py`); Nav2-compatible Pattern B exterior topic-remapping integration.  
**Safety concept baseline:** `SAFETY_CONCEPT.md` v0.11. This brief and the safety concept are aligned with the v2.4.2 / Gate Core v0.5 baseline at 22 November 2026; where they differ in detail, this brief describes the v2.4.2 package baseline.  
**ROS distribution:** ROS 2 Jazzy Jalisco on Ubuntu 24.04 Noble  
**Simulation baseline:** Webots R2025a, PAL Robotics TIAGo model  
**Repository:** <https://github.com/marunigno-ship-it/QERRA-v2-classical>  
**Archive DOI:** <https://doi.org/10.5281/zenodo.24053163>

---

## Executive Summary

QERRA-v2 Classical contains a deterministic supervisory gate and an assistive reflex input path intended to constrain velocity commands before they reach a mobile robot base controller. This brief covers only Layer 1A, the kinematic Supervisory Gate, and Layer 1B, the QERRA-HSR reflex companion. SEMEV-12 and QERRA-THRIVE are outside the physical safety function described here.

The implementation consists of three distinct elements:

1. **Gate Core v0.5:** a pure-Python decision kernel implemented in `gate/gate_core.py`. Its transition function is `step(state, params, inputs) -> StepResult`. It has no ROS 2 dependency, file access, socket access, or direct clock access. Time is supplied as an explicit integer input in microseconds.
2. **ROS 2 Jazzy adapter:** `ros2/qerra_gate_node.py`, packaged as `qerra_core` using `ament_python`. The node receives proposed velocity commands, laser scans and measured odometry, polls HSR telemetry over non-blocking UDP, evaluates the gate, and publishes a constrained `Twist` command and diagnostic state. It can optionally write a hash-chained flight log.
3. **QERRA-HSR reflex path:** a three-vector status source evaluating `immediate_physical_distress`, `human_isolation`, and `environmental_hazard_proximity`. The ROS 2 gate receives its `CLEAR`, `MONITOR`, or `CRITICAL` status over UDP port 5008. A pure-function stream monitor checks the packet sequence before the status reaches the core.

The gate uses a dynamic stopping envelope based on commanded wheel speed, a configured deceleration, a reaction-time allowance, and a fixed margin. It also checks lidar scan integrity and freshness, proposer freshness, clock progression, and HSR status. A detected trip holds the software wheel command at zero. Recovery from a latched trip requires a continuous clear interval (which, when `standstill_required=True`, also requires measured wheel standstill), a valid operator reset, and a quiescent reset tick before motion can resume.

**Gate Core v0.5: Doer-Checker separation and the Standstill Dwell Trap.** During Gate Core v0.5 hardening, generating an open-loop deceleration trajectory (`TRIP_BRAKING`) inside the Gate was explicitly evaluated and rejected. A supervisory safety monitor must remain a Checker, not a trajectory planner, and must never continue commanding non-zero forward velocity after a trip. The Gate Core therefore continues to command `(0, 0)` immediately upon any trip and leaves physical braking profiles to the base motion controller or drive subsystem. Instead, v0.5 resolves the **"Standstill Dwell Trap"** by gating the recovery calm dwell on measured velocity feedback. `GateParams` adds `standstill_required: bool = False` (default `False` for backward compatibility) and `w_standstill_tol_urad_s: int = 50_000` (0.05 rad/s, approximately 4.9 mm/s on 98 mm wheels). `GateInputs` adds optional integer fields `meas_left_urad_s` and `meas_right_urad_s`. When `standstill_required=True`, the 1.0 s calm dwell in `Mode.TRIPPED` starts only after confirmed physical standstill and resets to zero if motion resumes mid-dwell; missing feedback fails closed. The ROS 2 node subscribes to `/odom` (`nav_msgs/msg/Odometry`), converts the measured body twist to integer wheel speeds, and applies a 100 ms freshness watchdog with backward clock-jump protection. The Webots supervisory controller feeds wheel-sensor-derived measured speeds into the same inputs. `standstill_required` defaults to `False` in `GateParams`, `QerraGateNode` and `launch/qerra_gate.launch.py`, so the new recovery gating is opt-in outside the Webots controller (section 3.4, section 4.8). Measured speeds do not enter the stopping envelope, which is still computed from commanded velocity (section 6.3).

**Phase 1 non-finite Twist command inhibition:** `GateInputs` now includes `proposal_invalid: bool = False`, and `GateState` includes `proposal_inhibited: bool = False`. The ROS 2 adapter marks an incoming command invalid when `twist_to_proposal()` raises `ValueError` for non-finite `linear.x` or `angular.z` values (`NaN` or positive/negative infinity). On the first Gate Core tick that consumes this indication, the core emits `Event.MSG_REJECTED_INVALID`, sets `proposal_inhibited=True`, and commands `(0, 0)` while remaining in `Mode.RUN`. The previous held proposal timestamp is not refreshed. Inhibition remains active across inter-tick silence until a fresh valid finite proposal arrives, or until the existing 150 ms proposer freshness watchdog expires and escalates to `TRIP_PROPOSER_STALE`. Higher-priority obstacle and HSR trips retain precedence; inhibition does not clear `TRIPPED` or `AWAITING_RESET`. The event and input are included in flight-log records, with backward-compatible replay of earlier records that do not contain `proposal_invalid`.

**Layer 1B wire contract v0.4.0 and receiver diagnostics:** `gate/hsr_telemetry.py` v0.4.0 removes fail-open defaults by making `hazard_proximity` (`bool`) and `persons_nearby_count` (`int >= 0`) strictly mandatory in `parse_hsr_telemetry()`; `robot_task_interruptible` and natural-language recovery directives remain outside the Layer 1B wire contract. `ros2/hsr_receiver.py` maintains monotonic process-lifetime `packets_drained_total` and `packets_rejected_total` counters and preserves `last_rejection_reason` across `reset()`. Parser failures are mapped to fixed sanitized categories capped at 64 characters (`MAX_REJECTION_REASON_CHARS = 64`), without echoing untrusted wire data; Windows `WSAEMSGSIZE` (10040) and `WSAECONNRESET` (10054) are handled explicitly. `QerraGateNode` serializes `hsr_rejected_total` and `hsr_last_rejection_reason` into `/gate/state`. The standard-library `unittest` module `tests/test_hsr_conformance.py` sweeps 28,028 valid grid evaluations (`0..1000` permille × hazard × `0..6` persons × `robot_task_interruptible`) to check threshold-constant parity and exact 0.001-grid equivalence between `hsr/qerra_hsr.py` and `gate/hsr_telemetry.py`, alongside a 24-case rejected-payload matrix and a NaN asymmetry pin. `tests/test_hsr_receiver_diagnostics.py` verifies receiver counters and sanitized rejection categories across 8 tests.

The ROS 2 node defaults to a 32 ms control period (31.25 Hz), but the period is derived from `rate_hz` and propagated as `dt_us` into `get_live_gate_params()`. The factory derives `max_tick_gap_us = 2 * dt_us`, preserving dwell continuity when the configured control rate changes. The startup lidar invariant is evaluated using the actual control period. The standard launch entry point `launch/qerra_gate.launch.py` exposes all 15 node parameters as explicitly typed `ParameterValue` values, in addition to six configurable topic remappings (21 launch arguments in total).

The ROS 2 CI workflow builds and starts the standalone `qerra_core` package under ROS 2 Jazzy; `src/qerra_msgs` is masked from `colcon` discovery by `COLCON_IGNORE` and is not built or declared as a package dependency. The workflow verifies package and launch discovery, parameter arguments, live launch and executable startup, `/gate/state` publication, tick-exception absence, SIGINT shutdown and process cleanup. Regression tests cover 10 Hz `dt_us` propagation and dwell continuity, HSR receiver continuity across an accepted reset at 40 ms and 50 ms UDP periods, Phase 1 non-finite Twist inhibition and recovery, Gate Core v0.5 standstill-qualified dwell, and `/odom` ingestion with its freshness watchdog. Flight-log replay tests verify that invalid-proposal inhibition is reproduced bit-for-bit. DDS and UDP integration tests cover live topic traffic, dual-protocol reflex execution, remapping and the Nav2-compatible exterior command interface. CI steps use isolated `ROS_DOMAIN_ID` values and explicitly guarded ROS-dependent test modules (section 5.3).

At the v2.4.2 package metadata baseline on 22 November 2026 (main commit `5734dd7`), the author reports 266 host tests collected via standard-library `unittest discover` (252 passed, 14 cleanly skipped on hosts without `rclpy`, 0 failures), 50 passing tests in the native `ros:jazzy` container, and 20 separately passing QERRA-HSR tests under `hsr/` (section 5.2).

**Scope and safety status:** QERRA is an open-source simulation research prototype. The gate has been exercised in Webots R2025a, and the ROS 2 package has been built, started and exercised under live topic and UDP traffic in GitHub Actions Linux containers. The ROS 2 node has not been tested on a physical robot. No functional-safety certification, Performance Level, Safety Integrity Level, or standards conformity is claimed. A `0.0 m/s` output is a software velocity setpoint; it is not an emergency stop, a mechanical brake command, or a hardware Safe Torque Off (STO) function. Temporary command inhibition is also a software setpoint policy, not an instantaneous physical stop. References to ISO 13849-1, ISO 13482, ISO 3691-4 and EN 50159 are informative design references only. Localhost is treated as an assumed trusted process boundary (section 1.5); the gate does not defend against a hostile local process.


---

## 1. Architecture and Simplex Pattern

### 1.1 Functional partition

The architectural objective is to separate command generation from the final software decision to pass or clamp a velocity command. A planner, teleoperation source, or learned policy is treated as an untrusted proposer. The gate evaluates its proposal against independent sensor and reflex inputs before publishing the output setpoint. The node's default topics remain `/cmd_vel` and `/cmd_vel_safe`; for the tested Pattern B exterior configuration, node-specific ROS 2 remapping connects a Nav2-compatible proposer topic such as `/cmd_vel_nav` to the gate input and connects the gate output to a base-controller topic such as `/base/cmd_vel`. The measured-odometry input `/odom` (`nav_msgs/msg/Odometry`, QoS depth 10) feeds only the standstill-qualified recovery dwell and never the command path.

```text
             UNVERIFIED COMMAND PROPOSER
          (Nav2-compatible source, teleop, policy)
                              |
                              | /cmd_vel_nav
                              | (example remapped input)
                              v
       +------------------------------------------------+
       |              QERRA ROS 2 GATE NODE             |
       |                qerra_gate_node                 |
       |  default input /cmd_vel -> remapped input      |
       |  e.g. /cmd_vel_nav                             |
       |                                                |
       |  /scan -----------------> Lidar pipeline       |
       |  /odom -----------------> Wheel-speed feedback |
       |                           + freshness (100 ms) |
       |  UDP :5008 -------------> HSR receiver         |
       |                           + stream monitor     |
       |  /gate/reset -----------> Reset request        |
       |                                                |
       |  +------------------------------------------+  |
       |  | Gate Core v0.5                           |  |
       |  | step(state, params, inputs)               |  |
       |  | Standstill-qualified recovery dwell      |  |
       |  | Kinematic envelope / freshness / FSM     |  |
       |  +------------------------------------------+  |
       |                                                |
       |  NodeFaultLatch        optional flight log     |
       |  default output /cmd_vel_safe -> remapped     |
       |  output, e.g. /base/cmd_vel                   |
       +----------------------+-------------------------+
                              |
                              | /base/cmd_vel
                              | (example remapped output)
                              v
                 BASE CONTROLLER INTERFACE
                              |
                              v
                     MOTOR DRIVES / WHEELS

            /gate/state <---- diagnostic publication

       Node-specific remapping is configuration, not
       publisher authentication or actuator access control.
```

### 1.2 Separation of the ROS shell and the decision kernel

`gate/gate_core.py` is deliberately separated from ROS 2. The core receives explicit state, immutable parameters, and an input record. It returns a new state, wheel commands, a primary reason code, secondary events, and a record suitable for logging.

The core uses integer units for its decision and log quantities:

| Quantity | Representation |
|---|---|
| Time | microseconds (`us`) |
| Wheel angular speed (commanded, and from v0.5 optional measured) | microradians per second (`urad/s`) |
| Distance | millimetres (`mm`) |
| Linear speed used by the envelope | millimetres per second (`mm/s`) |

This separation supports deterministic unit testing and replay of the core without requiring a ROS 2 installation. It does not, by itself, establish a hard real-time execution guarantee for the ROS 2 process that calls it. The HSR stream monitor (`step_hsr_stream`) follows the same pattern: a pure function of its state, the drained packets and the current time.

### 1.3 Relationship to Simplex Architecture

QERRA uses a **Simplex-inspired supervisory pattern**: an unverified command source proposes an action, while a lower-complexity deterministic gate evaluates whether the command may be passed to the actuator interface. The pattern follows the runtime-assurance idea behind the Simplex architecture.

The term *Simplex-inspired* is intentional. This implementation is not presented as a formally verified or complete implementation of the original Simplex architecture. The current gate is a command supervisor based on a stopping-distance test, freshness checks, and latched recovery. It does not provide a separately verified backup motion controller, a formal proof of an invariant safe set, or a proof that every possible robot state can be driven into a safe region.

The Gate Core v0.5 decision to reject `TRIP_BRAKING` (section 3.4) is consistent with this positioning: the gate is a Checker that passes, clamps or zeroes a proposal; it does not generate a deceleration trajectory.

### 1.4 Actuator authority boundary

The ROS 2 node subscribes by default to `/cmd_vel` and publishes by default to `/cmd_vel_safe`. It is intended to be placed downstream of command multiplexing and upstream of the base controller. The installed launch file `launch/qerra_gate.launch.py` exposes configurable topic arguments; the tested Pattern B exterior configuration maps the node's input to `/cmd_vel_nav` and its output to `/base/cmd_vel`. The base controller must be configured to accept commands only from the gate output path. Any direct planner, teleoperation, or alternate publisher path to the base controller would bypass the supervisor.

The Nav2-compatible exterior tests use a harness that behaves as an external velocity proposer and a base-controller topic subscriber; they do not instantiate an actual Nav2 `controller_server`. In the active isolation canary, the harness publishes distinct `0.35 m/s` proposals to the unmapped default `/cmd_vel` while the gate's remapped proposal input is not being fed. The test checks that the default `/cmd_vel_safe` subscriber receives zero messages and that the latest observed `/base/cmd_vel` value, if one is present, is not the injected `0.35 m/s` proposal. This is evidence for the tested remapping configuration and observation window, not a proof of graph-wide publisher exclusivity or protection against every possible alternate publisher.

ROS 2 topic naming and ordinary publish/subscribe operation do not, by themselves, enforce exclusive write authority. The node uses absolute topic names by default and does not configure SROS2 permissions or cryptographic publisher authentication. Therefore:

- Exclusive actuator authority is demonstrated in the Webots supervisory-controller topology, where the gate is the only process writing the simulated wheel velocities.
- In the standalone ROS 2 implementation, the gate publishes the designated output topic, and the tested node-specific remappings connect that output to `/base/cmd_vel`; exclusive authority remains a deployment requirement, not an access-control property established by the node.
- A physical integration would need an enforced command topology, controlled remapping, namespace isolation, DDS security policies, and protection against alternate command publishers.

The ROS 2 adapter should not be described as having proven exclusive physical actuator authority until this deployment boundary is enforced and tested.

### 1.5 Trust boundary

The project assumes that every process able to send to the gate's localhost UDP ports (5005, 5006, 5008) or to publish on its ROS topics is trusted. This is an assumption, not an achievement. The channels carry no authentication, no integrity code and no sender identity, and the node configures no SROS2 policy.

Protection against a hostile or compromised local process belongs outside the gate node: operating-system file permissions and user separation, exclusive socket binding, and SROS2 or equivalent access control on the ROS graph. In particular, a hostile process that can publish to `/cmd_vel_safe` bypasses the gate entirely, and no UDP authentication added to the gate would change that. The same applies to `/odom`: a process able to publish forged odometry could report standstill while the robot moves, defeating the standstill qualification when it is enabled.

Within this assumption the core still refuses malformed or out-of-order inputs: it drops malformed and causality-violating telemetry, rejects a reset that does not come from the operator source, and refuses resets during the dwell or while a hazard is present (section 5.5). Section 6.6 describes a sequence of well-formed forged inputs that this design does not defend against, and which an executable test demonstrates.

---

## 2. Kinematic Stopping Envelope and Corridor Filter

### 2.1 Stopping-distance calculation

The gate evaluates obstacle clearance against a stopping-distance envelope recalculated from a reference velocity on each control tick.

In integer millimetre units:

$$
d_{\mathrm{stop,mm}}(v) =
\left\lceil \frac{v_{\mathrm{mm/s}}^2}{2\,a_{\mathrm{design,mm/s^2}}} \right\rceil
+
\left\lceil \frac{v_{\mathrm{mm/s}}\,t_{\mathrm{react,us}}}{10^6} \right\rceil
+ m_{\mathrm{mm}}
$$

The gate parameters are:

| Parameter | Value | Interpretation |
|---|---:|---|
| `a_design_mmps2` | 500 mm/s^2 | Design deceleration, equivalent to 0.5 m/s^2 |
| `t_react_us` | 32,000 us (Webots controller); 96,000 us (ROS 2 node default, parameter `t_react_ms`) | Reaction-time allowance; see section 4.2 |
| `margin_mm` | 300 mm | Fixed standstill clearance margin |
| `dt_us` | 32,000 us at 31.25 Hz; 100,000 us at 10 Hz | Control period derived from `rate_hz` by `QerraGateNode` |
| `t_watch_us` | 150,000 us | Proposer freshness limit |
| `t_stale_us` | 96,000 us (Webots and the ROS 2 simulation profile); 300,000 us (ROS 2 hardware profile) | Lidar freshness limit; node parameter `lidar_stale_ms` |
| `t_hsr_stale_us` | 96,000 us | HSR telemetry freshness limit |
| `t_dwell_us` | 1,000,000 us | Continuous-clear dwell before reset can be accepted |
| `max_tick_gap_us` | `2 * dt_us`: 64,000 us at 31.25 Hz; 200,000 us at 10 Hz | Maximum inter-tick gap accepted during a continuous dwell |
| `standstill_required` | `False` (default) | Gate Core v0.5: when `True`, the recovery calm dwell requires measured wheel standstill (section 3.4) |
| `w_standstill_tol_urad_s` | 50,000 urad/s (0.05 rad/s, approximately 4.9 mm/s on 98 mm wheels) | Gate Core v0.5: per-wheel standstill tolerance |

The Webots controller passes a 32,000 us reaction allowance explicitly. In the ROS 2 node, `QerraGateNode` computes `self._dt_us` from `rate_hz` as the nominal timer period in microseconds, then passes `dt_us=self._dt_us` to `get_live_gate_params()`. The factory sets `max_tick_gap_us = 2 * dt_us`. Thus the default `rate_hz=31.25` gives `dt_us=32,000` and `max_tick_gap_us=64,000`; a configured `rate_hz=10.0` gives `dt_us=100,000` and `max_tick_gap_us=200,000`. This scaling is required for continuous-clear dwell tracking to remain valid when the configured control period changes. The generic `GateParams` data class retains a zero reaction-time default for backward compatibility.

The reference speed is derived from the larger positive wheel speed among the previous commanded wheel output and the newly clamped proposal. The core converts this wheel angular speed to a linear wheel speed using the configured wheel radius. Gate Core v0.5 does not change this: measured wheel speeds feed only the recovery-dwell standstill qualification (section 3.4) and not the stopping envelope (section 6.3).

**AR-2 Option A — symmetrical reverse rejection:** with `w_min_urad_s = 0`, if either held wheel proposal is below the minimum (requests reverse rotation), the core sets both wheel commands to `(0, 0)`. This prevents a one-wheel reverse request from becoming an unmonitored pivot or arc when rearward sensor coverage is absent. A proposal that is clamped this way can still produce `Reason.PASS`: `PASS` means that no trip condition fired on that tick; it does not mean that the proposal passed through unchanged. The actual clamped values are exposed as `cmd_left_urad_s` and `cmd_right_urad_s` in `/gate/state` diagnostics.

### 2.2 Nominal cruise calculation

For equal wheel speeds of 2.0 rad/s and a wheel radius of 0.098 m, the linear speed is 0.196 m/s (196 mm/s). With a design deceleration of 0.5 m/s^2, the braking term is

$$
d_{\mathrm{brake}} = \left\lceil \frac{196^2}{2 \times 500} \right\rceil = \lceil 38.416 \rceil = 39\ \mathrm{mm}.
$$

The reaction term and total depend on the configured reaction time:

| Configuration | `t_react` | Braking | Reaction | Margin | `d_stop` at 196 mm/s | `d_stop` at 200 mm/s |
|---|---:|---:|---:|---:|---:|---:|
| Webots controller | 32 ms | 39 mm | 7 mm | 300 mm | 346 mm | 347 mm |
| ROS 2 simulation profile (default) | 96 ms | 39 mm | 19 mm | 300 mm | 358 mm | 360 mm |
| ROS 2 hardware profile (10 Hz scanner) | 160 ms | 39 mm | 32 mm | 300 mm | 371 mm | 372 mm |

The 196 mm/s column is the nominal TIAGo cruise used in the Webots runs. The 200 mm/s column is the rounded figure used in the profile definitions; at 200 mm/s the braking term is 40 mm. The 346 mm figure at 196 mm/s is the envelope in Demo 8 and Demo 9.

These are the configured software envelopes at the stated commanded speed. They are not measured physical stopping-distance guarantees.

### 2.3 Lidar corridor filter

`gate/gate_lidar.py` provides a forward corridor filter. The current node defaults are:

- Expected scan length: 682 range samples.
- Configured field of view: 240 degrees.
- Corridor half-width: 0.32 m.
- Robot base half-width assumption: 0.27 m.
- Additional lateral allowance: 0.05 m.

The resulting nominal corridor width is 0.64 m. The filter treats the scan samples as evenly distributed over a symmetric field of view. For each valid range, it determines whether the corresponding projected point lies ahead of the sensor and within the configured lateral half-width. Valid points outside that corridor are replaced with positive infinity (`+inf`), leaving the array length unchanged. Invalid values are not converted into clear readings; they are passed to the core for rejection.

The core validates scan presence, sample count, timestamp age, values, and the minimum raw return count. A sample-count mismatch is discarded by the ROS 2 adapter and results in a fail-closed sensor-invalid condition. The current live configuration requires at least five finite raw returns across the scan. The Webots TIAGo lidar reports 667 samples, so a Webots run with this node needs the `lidar_n_expected` parameter set to 667.

The corridor filter is a straight-ahead translational approximation. It does not compute the full swept footprint of a differential-drive robot during a turn, pivot, or curved trajectory. The present geometry must not be treated as a complete collision model for arbitrary motion.

### 2.4 Sensor geometry and integrity boundary

The default 682-sample, 240-degree profile is a configured sensor profile associated with the stated Hokuyo URG-04LX baseline. The ROS 2 callback checks the number of range samples. It does not currently establish that the incoming `LaserScan` metadata (`angle_min`, `angle_increment`, `angle_max`, frame transform, or acquisition timing) matches the configured geometry.

A scan with the expected number of samples but a different angular layout could therefore be interpreted using incorrect beam geometry. A physical integration must validate the actual scanner configuration, frame transform, angular metadata, timing, valid-range limits, and mounting orientation. A sample-count check alone is not a complete sensor-geometry integrity check.

The minimum raw-return count is also a global scan-liveness test. Returns from lateral walls can satisfy the minimum even if the forward sector is obscured. Forward-sector visibility needs a separate coverage or diagnostic criterion before the filter can be relied upon for physical obstacle coverage.

---

## 3. Deterministic State Machine and Recovery Contracts

### 3.1 Gate Core states

The Gate Core finite state machine has three operational modes:

- `RUN`
- `TRIPPED`
- `AWAITING_RESET`

The initial `GateState` is fail-closed and starts in `TRIPPED`. The node-level diagnostic value `FAULT` is produced by `NodeFaultLatch`; it is not a fourth mode in the Gate Core enum. `GateState` also carries the Boolean `proposal_inhibited` state. This is an inhibition flag within the existing `RUN` mode, not a fourth operational mode and not a latched trip by itself.

The existing operational Gate Core transitions remain:

```text
                    +------------------+
                    |       RUN        |
                    +---------+--------+
                              |
                    trip condition detected
                              |
                              v
                    +------------------+
              +---->|     TRIPPED      |<----+
              |     +---------+--------+     |
              |               |              |
              |       continuous clear      |
              |       dwell satisfied       |
              |       and HSR clear dwell   |
              |               |              |
              |               v              |
              |     +------------------+     |
              +-----|   AWAITING_RESET  |-----+
                    +---------+--------+  hazard reappears,
                              |           or dwell invalidated
                       valid operator reset
                              |
                              v
                    +------------------+
                    | RUN, zero output |
                    | for this tick    |
                    +---------+--------+
                              |
                         next RUN tick
                              |
                              v
                    +------------------+
                    |       RUN        |
                    +------------------+

       Node-level fault latch: separate process-lifetime overlay.
       When latched, it reports FAULT and commands zero on later ticks.
```

When `standstill_required=True` (Gate Core v0.5), the `TRIPPED` to `AWAITING_RESET` guard additionally requires confirmed measured wheel standstill throughout the clear dwell; motion detected mid-dwell resets the dwell countdown (section 3.4). The mode set and transitions in the diagram are otherwise unchanged.

Temporary proposal inhibition is an overlay within `RUN`, not an additional operational mode. When a non-finite Twist has been observed and the corresponding `proposal_invalid=True` input is processed, the core sets `proposal_inhibited=True` and commands both wheel speeds to zero while remaining in `RUN`. The inhibition is retained in Gate Core state across later ticks with no new proposal. A fresh valid proposal clears the inhibition automatically; if the held proposal reaches the existing 150 ms freshness limit first, the ordinary proposer-stale trip transitions the gate to `TRIPPED`. `TRIP_OBSTACLE` and `TRIP_HSR_CRITICAL` take precedence, and invalid input does not clear an existing `TRIPPED` or `AWAITING_RESET` recovery state.

```text
                    +------------------+
                    |       RUN        |
                    +---------+--------+
                              |
                 invalid Twist indication
                              |
                              v
                    +------------------+
                    | RUN / INHIBITED  |
                    | output = (0, 0)  |
                    +----+---------+---+
                         |         |
       fresh valid       |         | proposer age reaches
       proposal          |         | 150 ms watchdog
       returns           |         |
                         v         v
                 +-----------+  +------------------+
                 |    RUN    |  |     TRIPPED      |
                 | inhibition|  | normal latched   |
                 | cleared   |  | recovery applies |
                 +-----------+  +------------------+

       `TRIP_OBSTACLE` and `TRIP_HSR_CRITICAL` take precedence
       over temporary inhibition.
       Invalid input does not clear an existing recovery latch.

       Node-level fault latch: separate process-lifetime overlay.
       When latched, it reports FAULT and commands zero on later ticks.
```

The second diagram shows the Phase 1 invalid-proposal path within the existing operational state machine; the node-level `FAULT` overlay remains separate.

### 3.2 Fail-closed trip conditions

The core evaluates the following conditions and returns a primary reason code for the tick:

| Reason | Trigger condition |
|---|---|
| `TRIP_OBSTACLE` | Minimum valid range in the filtered forward corridor is less than or equal to the stopping envelope |
| `TRIP_PROPOSER_DEAD` | No valid proposal has been accepted |
| `TRIP_PROPOSER_STALE` | Proposal age is greater than or equal to 150 ms |
| `TRIP_SENSOR_INVALID` | Missing scan, wrong sample count, stale or future scan timestamp, invalid range values, or insufficient raw returns |
| `TRIP_HSR_CRITICAL` | HSR reports `CRITICAL` |
| `TRIP_HSR_STALE` | Required HSR telemetry age exceeds 96 ms |
| `TRIP_HSR_INVALID` | Required HSR status is missing, malformed, or not one of the defined states; also the result when the stream monitor reports a frozen frame (section 3.5) |
| `TRIP_CLOCK_ANOMALY` | The supplied gate timestamp is not strictly greater than the previous tick timestamp |
| `TRIP_LOG_FAILURE` | The caller reports a log-write failure to the core (section 4.5) |

The proposer threshold is 150,000 us. The lidar freshness limit is the `t_stale_us` value for the active profile; the HSR freshness limit is 96,000 us. In the core implementation, HSR staleness is triggered when the age is greater than 96,000 us; a future-dated HSR observation is invalid. These are limits, not latency bounds: a trip follows once the age exceeds the limit and the next tick evaluates it.

Measured wheel speed (`meas_left_urad_s`, `meas_right_urad_s`) is not a trip condition. Missing or stale measured speeds do not create a `TRIP_*` reason; with `standstill_required=True` they only prevent the recovery calm dwell from running (section 3.4).

**Non-finite proposal handling is a temporary inhibition, not a new trip reason.** `GateInputs` has `proposal_invalid: bool = False`. When it is true, the core emits the secondary event `MSG_REJECTED_INVALID`, sets `GateState.proposal_inhibited=True`, and commands `(0, 0)` on the control tick that processes the indication while the operational mode remains `RUN`. The held proposal's `sim_stamp_us` is not refreshed by the invalid input. The zero output persists across inter-tick silence because the inhibition is stored in `GateState`; a fresh valid proposal clears it, while expiry of the existing 150,000 us proposal-age limit escalates through `TRIP_PROPOSER_STALE`. `TRIP_OBSTACLE` and `TRIP_HSR_CRITICAL` take precedence. When the gate is already `TRIPPED` or `AWAITING_RESET`, an invalid proposal does not clear or bypass that recovery state. The distinction between the `MSG_REJECTED_INVALID` event and a primary `TRIP_*` reason is intentional: one invalid sample does not by itself require operator-reset recovery.

The core uses an explicit timestamp input. This makes its transition function reproducible for the same state, parameters, and input tuple. It does not make the ROS executor or operating-system scheduling deterministic.

### 3.3 HSR integration

The QERRA-HSR companion evaluates three normalized context vectors:

1. `immediate_physical_distress`
2. `human_isolation`
3. `environmental_hazard_proximity`

The ROS 2 node receives HSR status telemetry through a non-blocking UDP receiver on port 5008, bound to the local host. The receiver drains queued datagrams, passes the raw arrival-ordered batch through the stream monitor (section 3.5), and then applies worst-severity reduction (`CRITICAL` over `MONITOR` over `CLEAR`) to the batch. When HSR is required, a valid and fresh HSR status is part of the gate's input contract. `CRITICAL` causes a gate trip. Missing, stale, future-dated, or invalid required telemetry also causes a fail-closed trip.

**`MONITOR` semantics:** In `Mode.RUN`, `hsr_status == "MONITOR"` imposes **no velocity cap** inside `gate_core.py`. The existing `3.0 rad/s` wheel envelope at a `98 mm` wheel radius bounds the nominal wheel-derived linear speed at `0.294 m/s`; Speed and Separation Monitoring cannot be justified from the current HSR wire packet because it carries no metric person-distance measurement. `MONITOR` acts fail-closed in recovery: it resets `hsr_clear_since_us` and rejects operator resets with `RESET_REJECTED_HAZARD` while the Gate is latched in `Mode.TRIPPED` or `Mode.AWAITING_RESET`.

**HSR wire contract v0.4.0:** `parse_hsr_telemetry()` requires all six wire fields: `obs_id`, `t_obs_us`, `t_emit_us`, `distress_permille`, `hazard_proximity`, and `persons_nearby_count`. The last two fields have no fail-open defaults at the parser boundary. A declared `state`, when supplied, must agree with the state derived from the telemetry values. The receiver maps parser rejection to nine fixed sanitized categories: `invalid_utf8`, `invalid_json`, `missing_required_field`, `timestamp_causality_error`, `future_observation_timestamp`, `state_mismatch`, `invalid_declared_state`, `oversized_datagram`, and `invalid_telemetry`; each diagnostic is capped at 64 characters and does not echo untrusted wire text.

The default HSR freshness ceiling is `t_hsr_stale_us = 96,000 us` (96 ms). A nominal 10 Hz producer (100 ms between frames) exceeds this ceiling on ordinary inter-packet intervals and causes `TRIP_HSR_STALE` before the next frame can refresh the status. For practical operating margin under the default threshold, the nominal HSR producer rate should be at least 20 Hz (period no greater than 50 ms). This is a practical nominal minimum intended to leave room for scheduling and transport jitter; it is not a guarantee of sensor-to-gate latency or a physical timing bound.

HSR does not replace lidar obstacle geometry. The lidar path evaluates physical range in the forward corridor; HSR evaluates the supplied human-distress and contextual reflex status. The simulation demonstrations use synthetic or injected HSR inputs. They do not demonstrate validated perception of distress in a physical environment.

The ROS 2 node defaults to `hsr_source="udp"` and `hsr_required=true`. Explicit obstacle-only operation requires `hsr_source="none"` with `hsr_required=false`; the node rejects the contradictory configuration in which HSR is required but its source is disabled. The stream monitor's trips act through the gate's required-HSR path, so with `hsr_required=false` they do not stop the robot.

### 3.4 Recovery contract and standstill qualification

A trip does not clear automatically when the immediate hazard disappears. Recovery is latched and requires:

1. The active trip conditions to clear.
2. An unbroken gate-level calm dwell of 1,000,000 us.
3. When `standstill_required=True` (Gate Core v0.5): confirmed measured wheel standstill, evaluated by `is_at_standstill()`. The calm dwell countdown starts only after standstill is confirmed and restarts from zero if motion is detected mid-dwell. Missing measured feedback fails closed, so the dwell cannot run without it.
4. Continuous valid HSR `CLEAR` status for the required HSR clear-dwell interval when HSR is enabled.
5. Tick continuity: a gap greater than `max_tick_gap_us = 2 * dt_us` invalidates continuity for the gate dwell. This is 64,000 us at the default 31.25 Hz (`dt_us=32,000`) and 200,000 us when `rate_hz=10.0` (`dt_us=100,000`).
6. An explicit reset request whose source string is `operator`.
7. No active obstacle or HSR hazard at the time reset is evaluated.

A reset from any other source is rejected with `RESET_REJECTED_CHANNEL`. A reset while the gate is not ready is rejected with `RESET_REJECTED_NOT_READY`. A reset while an obstacle or non-clear HSR condition persists is rejected with `RESET_REJECTED_HAZARD`. The node-level ROS callback accepts the case-insensitive, whitespace-trimmed string `operator` on `/gate/reset`; this is a command convention, not proof of the sender's identity.

On the exact tick when reset is accepted, the core remains quiescent and returns zero wheel commands with reason `RESET_ACCEPTED`. The held proposal is not applied on that tick. Motion can resume on the subsequent nominal `RUN` cycle if the current inputs remain valid and no trip condition is present.

After `RESET_ACCEPTED`, `QerraGateNode` preserves the existing `HsrReceiver` state; it does not call `HsrReceiver.reset()` from `_tick_callback()`. The core has already required `hsr_dwell_ok`, which represents 1.0 s of unbroken, fresh `CLEAR` HSR frames. Resetting the receiver at this point would erase its last valid status and stream state, creating a phase-dependent `TRIP_HSR_INVALID` on the first post-reset `RUN` tick when UDP frames arrive more slowly than the 31.25 Hz gate tick. Preserving the receiver state allows the next poll to continue the existing stream; the normal 96,000 us HSR freshness check remains active. The 40 ms and 50 ms period cases are covered by regression tests (section 5.2).

The HSR implementation also has its own stabilization logic. Where that upstream stabilization and the gate's independent clear dwell are both active, recovery is intentionally staged rather than immediate.

**Gate Core v0.5 standstill qualification (`gate/gate_core.py`).** The "Standstill Dwell Trap" is a recovery-timing problem: the gate commands `(0, 0)` immediately on a trip, but a robot that is still physically moving (coasting under the base controller's own deceleration) could have its calm dwell elapse while it is in motion. v0.5 resolves this by qualifying the dwell on measured wheel speed:

- `GateParams` gains `standstill_required: bool = False` (default `False` for backward compatibility) and `w_standstill_tol_urad_s: int = 50_000` (50,000 urad/s = 0.05 rad/s, approximately 4.9 mm/s on 98 mm wheels).
- `GateInputs` gains optional integer fields `meas_left_urad_s: Optional[int] = None` and `meas_right_urad_s: Optional[int] = None`.
- The pure integer predicate `is_at_standstill(params, left, right)` returns `not params.standstill_required` when either input is `None`; otherwise it requires integer types and `abs(left) <= w_standstill_tol_urad_s and abs(right) <= w_standstill_tol_urad_s`. With `standstill_required=True`, absent feedback therefore evaluates as not-at-standstill.
- In `step()`, the `Mode.TRIPPED` transition forces `clear_since_us` to `None` when the standstill condition is not met. The 1.0 s calm dwell countdown therefore starts only after confirmed physical standstill and resets to zero immediately if motion resumes mid-dwell.
- `_record()` logs `meas_left_urad_s` and `meas_right_urad_s` inside `rec["inputs"]`. `gate/gate_log.py` `reconstruct_inputs()` deserializes both with `.get(...)` defaults of `None`, so historical logs that predate v0.5 replay bit-for-bit unchanged (section 4.5).

**Architectural decision: Doer-Checker separation versus `TRIP_BRAKING`.** During v0.5 hardening, generating an open-loop deceleration ramp (`TRIP_BRAKING`) inside the Gate was explicitly evaluated and rejected. A supervisory safety monitor must remain a Checker, not a trajectory planner. Continuing to command non-zero forward velocity after a trip would contradict the fail-closed contract, and a gate-generated ramp would make the gate responsible for a motion profile it cannot verify against the actual drive. The Gate Core therefore continues to output `(0, 0)` immediately upon any trip, and physical braking profiles remain the responsibility of the base motion controller or drive subsystem. The qualification above only delays the start of recovery; it does not alter what the gate commands.

The regression class `TestStandstillDwellQualification` in `tests/test_gate_core.py` (4 tests, bringing the module to 65) verifies dwell inhibition while wheels turn, dwell activation after standstill, mid-dwell motion reset, and fail-closed inhibition on missing feedback when `standstill_required=True` (section 5.2).

### 3.5 Perception stream monitor and controlled rebase

The HSR telemetry carries a monotonic frame counter (`obs_id`). The pure function `step_hsr_stream(state, packets, now_us)` in `gate/hsr_telemetry.py`, with its state type `HSRStreamState`, is called by `HsrReceiver` in `ros2/hsr_receiver.py`. It was designed against four failure modes:

| Failure mode | Behaviour |
|---|---|
| Held values counted as fresh | A repeated `obs_id` (equal to the last one seen) sets a sticky frozen-frame fault. The receiver then presents no valid status, which trips `TRIP_HSR_INVALID` when HSR is required. |
| Reducer hides sequence faults | The raw datagrams are examined in arrival order, and sequence continuity is evaluated across every packet before worst-severity reduction is applied. |
| Producer restart or backlog replay | A counter regression (`obs_id` lower than the last one seen) trips fail-closed and flushes the operating-system UDP receive buffer, discarding datagrams queued before the restart. |
| Rebase accepted too cheaply | See the dwell conditions below. |

After a regression the receiver accepts the new sequence only when both of these hold:

1. The rebase streak has reached 5 control ticks, with at most one streak credit awarded per tick.
2. The observed duration, `t_obs_current - t_obs_start`, is at least 160,000 us. A boundary test checks that 159 ms is rejected and 160 ms is accepted.

Any `MONITOR` or `CRITICAL` packet, and any packet that does not strictly advance the counter, resets the streak to zero. The rebase only decides when fresh `CLEAR` frames may reach the gate again. It does not shorten or replace the gate's own recovery: the core keeps its 1.0 s continuous-clear dwell and still requires an explicit `operator` reset before `RUN` can be restored.

The duration condition uses the producer's own `t_obs_us` stamps, not a clock owned by the gate. The 5-tick condition runs on the gate's control ticks. The brief makes no claim about producer session identity, a cap on rebases per time window, or the handling of duplicated or gapped packets within the rebase dwell. The monitor adds no sender authentication (section 6.6).

---

## 4. ROS 2 Node Hardening, Timing Profiles and Fault Latching

### 4.1 Package and node boundary

The ROS 2 package is `qerra_core`, built with `ament_python` and described by a ROS package manifest using package format 3. The manifest declares `<exec_depend>` entries for `launch`, `launch_ros` and `nav_msgs`. The node entry point is `ros2/qerra_gate_node.py`, with `NODE_VERSION = "0.3.1"`. It wraps Gate Core v0.5 and uses the following interfaces. The default topic names in this table can be changed through the launch file's topic remapping arguments (section 4.7):

| Interface | Type | Role |
|---|---|---|
| `/cmd_vel` | `geometry_msgs/msg/Twist` | Proposed body velocity; non-finite `linear.x` or `angular.z` values are rejected and reported to Gate Core as an invalid-proposal indication |
| `/scan` | `sensor_msgs/msg/LaserScan` | Lidar range input. The subscription uses `qos_profile_sensor_data` (Best Effort, Volatile) so that it matches physical lidar drivers. |
| `/odom` | `nav_msgs/msg/Odometry` (QoS depth 10) | Measured body twist, converted to integer wheel speeds and used only for the standstill-qualified recovery dwell (Gate Core v0.5) |
| `/gate/reset` | `std_msgs/msg/String` | Operator reset request |
| `/cmd_vel_safe` | `geometry_msgs/msg/Twist` | Gate output setpoint, including zero output during temporary proposal inhibition |
| `/gate/state` | `std_msgs/msg/String` | JSON diagnostic state |
| UDP port 5008 | QERRA-HSR telemetry | Reflex state input |
| UDP port 5007 | Gate clock/state message | Simulation producer clock interface |

Because the `/scan` subscription is Best Effort, scan messages can be dropped in transit. A dropped scan is not interpolated; the scan-freshness limit (section 3.2) is what turns a sustained loss into `TRIP_SENSOR_INVALID`.

`_cmd_vel_callback()` calls `twist_to_proposal()`. If conversion raises `ValueError` for a non-finite `linear.x` or `angular.z`, the callback sets `self._latest_proposal = None` and `self._proposal_invalid = True`; a valid finite Twist stores the converted proposal and resets the invalid flag to `False`. `_tick_callback()` transfers the invalid indication into `GateInputs.proposal_invalid` for Gate Core evaluation. This keeps ROS-message parsing in the adapter and the deterministic inhibition decision in the pure-function core.

`GateInputs` includes `proposal_invalid: bool = False`, and `GateState` includes `proposal_inhibited: bool = False`. During `RUN`, an invalid indication causes `MSG_REJECTED_INVALID`, sets the inhibition state and produces `(0, 0)` wheel output on the tick that consumes the indication without changing the mode to `TRIPPED`. The previous held proposal timestamp is not refreshed. Inhibition persists through later ticks without a new valid proposal until a fresh finite proposal clears it or the 150 ms proposer watchdog escalates to `TRIP_PROPOSER_STALE`. `TRIP_OBSTACLE` and `TRIP_HSR_CRITICAL` take precedence; an invalid proposal cannot release `TRIPPED` or `AWAITING_RESET` (sections 3.1 and 3.2).

**`/odom` ingestion and freshness watchdog.** `_odom_callback()` reads `msg.twist.twist.linear.x` and `msg.twist.twist.angular.z`, converts them with `twist_to_wheel_speeds()` (using the node's configured `track_width_m` and `wheel_radius_m`) into the integer values `_meas_left_urad_s` and `_meas_right_urad_s`, and stamps `_odom_stamp_us = self._get_ros_time_us()` at the moment of receipt. A non-finite or malformed message sets both measured values to `None`. Before the first `/odom` message the measured values are also `None`. In `_tick_callback()`, before `GateInputs` is built, the node applies a freshness watchdog with `DEFAULT_ODOM_STALE_US = 100_000` us (100 ms): it computes `odom_age_us = now_us - self._odom_stamp_us`, and if `odom_age_us < 0 or odom_age_us > 100_000` the measured speeds for that tick are reset to `None`. The negative-age branch protects against a backward ROS-clock jump (for example a simulation-time reset), which would otherwise leave an old measurement looking fresh. A `None` measurement blocks the recovery dwell when `standstill_required=True`, and has no effect on the dwell when it is `False`.

`/gate/state` carries the node and gate versions, the mode (`RUN`, `TRIPPED`, `AWAITING_RESET`, or `FAULT`), the reason, the list of secondary `events` (including `MSG_REJECTED_INVALID` for a rejected non-finite Twist and reset-related events), `d_stop_mm`, `lidar_min_mm`, the HSR status and configuration (`hsr_source`, `hsr_required`, `hsr_drained_total`, `hsr_rejected_total`, `hsr_last_rejection_reason`, `hsr_socket_error`), the recovery configuration flag `standstill_required`, HSR stream-monitor diagnostics (`hsr_frozen`, `hsr_rebase_in_progress`, `hsr_rebase_streak`), `fault_latched` and `fault_reason`, proposal sequence and age, the wheel commands `cmd_left_urad_s` and `cmd_right_urad_s`, and the active timing parameters `t_react_us`, `lidar_stale_us` and `lidar_period_us`. `hsr_last_rejection_reason` is a fixed sanitized category capped at 64 characters; untrusted wire text is not echoed. The wheel-command fields report the final values after AR-2, envelope clamping and temporary proposal inhibition, not necessarily the raw proposal. The measured wheel speeds are not published in `/gate/state`; `standstill_required` reports configuration, not the current standstill status.

The node exposes 15 parameters:

| Parameter | Default | Meaning |
|---|---|---|
| `rate_hz` | 31.25 | Nominal tick rate (32 ms period) |
| `track_width_m` | 0.4044 | TIAGo wheel-track separation in metres |
| `wheel_radius_m` | 0.098 | TIAGo drive-wheel radius in metres |
| `robot_half_width_m` | 0.32 | Corridor half-width in metres |
| `lidar_n_expected` | 682 | Required beam count per scan |
| `lidar_fov_rad` | 4.1887902 | Scan field of view (240 degrees) |
| `t_react_ms` | 96.0 | Reaction-time allowance (finite and non-negative) |
| `lidar_period_ms` | 32.0 | Assumed scan period |
| `lidar_stale_ms` | 96.0 | Scan freshness limit |
| `hsr_source` | `udp` | `udp`, or `none` for explicit obstacle-only mode |
| `hsr_port` | 5008 | UDP port for HSR datagrams |
| `hsr_required` | true | Trip if HSR telemetry is missing or stale |
| `standstill_required` | false | Require measured wheel standstill for the recovery calm dwell (Gate Core v0.5); passed to `get_live_gate_params()` |
| `state_port` | 5007 | UDP port for the clock echo |
| `flight_log_path` | empty (disabled) | Path of the hash-chained flight log |

The control period is derived from `rate_hz`: at the default 31.25 Hz, `dt_us = 32,000` and `max_tick_gap_us = 64,000`; at 10.0 Hz, `dt_us = 100,000` and `max_tick_gap_us = 200,000`. `QerraGateNode` stores the computed value in `self._dt_us` and passes it into `get_live_gate_params()`, which sets the maximum inter-tick dwell gap to twice the period. The default node timer period is 1/31.25 s, or 32 ms. This is a configured nominal period, not a measured worst-case dispatch interval.

### 4.2 Timing profiles and startup invariant

Three timing parameters (`t_react_ms`, `lidar_period_ms`, `lidar_stale_ms`) replace the single 32 ms Webots assumption. The node derives `dt_ms` from `rate_hz` and enforces at startup, refusing to start if it is violated, the invariant:

```text
lidar_stale_ms >= 2 * lidar_period_ms + dt_ms
```

The two documented lidar timing profiles are:

| Profile | `lidar_period_ms` | `lidar_stale_ms` | `t_react_ms` | Assumed node period | `d_stop` at 196 mm/s |
|---|---:|---:|---:|---:|---:|
| Simulation (default) | 32.0 | 96.0 | 96.0 | 32 ms (`rate_hz=31.25`) | 358 mm |
| 10 Hz Hokuyo URG-04LX scanner profile | 100.0 | 300.0 | 160.0 | 32 ms (`rate_hz=31.25`) | 371 mm |

At the default node rate `rate_hz=31.25`, `dt_ms=32`. Both scanner profiles satisfy the startup invariant: `96 >= 2 * 32 + 32`, and `300 >= 2 * 100 + 32`. The 10 Hz scanner profile does not by itself mean that the gate control timer runs at 10 Hz; it assumes the default 31.25 Hz node rate unless `rate_hz` is changed.

When the node itself is configured at `rate_hz=10.0`, `dt_ms=100`. With the 10 Hz scanner values (`lidar_period_ms=100.0`, `lidar_stale_ms=300.0`), the invariant becomes `300 >= 2 * 100 + 100`, and the configured `max_tick_gap_us` is 200,000 us. The 10 Hz node regression test uses this parameter combination. It verifies parameter propagation and dwell-gap arithmetic; it is not a measurement of executor timing or a real-time performance guarantee. A 10 Hz HSR producer is still too slow for the fixed 96 ms HSR freshness ceiling (section 3.3); the lidar-rate profile and the HSR producer-rate requirement are separate contracts.

The reaction-time values come from an engineering estimate of the signal chain, not from measurement:

| Component | Simulation | 10 Hz hardware | Basis |
|---|---|---|---|
| Scan period | 32 ms | 100 ms | Sensor update period |
| Transport | 2 to 4 ms | 2 to 4 ms | Estimate |
| Gate evaluation | 32 ms | 32 ms | One control period at `rate_hz=31.25` |
| Scheduling jitter | 10 to 15 ms | 10 to 15 ms | Estimate |
| Actuator response | 10 to 15 ms | 10 to 15 ms | Estimate |
| **Total** | **86 to 98 ms** | **154 to 166 ms** | |

The profile values (96 ms and 160 ms) lie inside these ranges. They are mid-range values, not upper bounds. The estimate for the 10 Hz scanner profile assumes the gate itself continues to tick at 31.25 Hz. If `rate_hz` is changed to 10.0, the gate-evaluation component becomes a nominal 100 ms period rather than 32 ms; the 154 to 166 ms estimate and its 160 ms setting must not be carried over as a validated reaction-time budget. The complete reaction-time estimate and `t_react_ms` must be re-derived for that control rate. Section 6.2 describes what the present estimates do and do not establish.

### 4.3 NodeFaultLatch

`NodeFaultLatch` is a pure-Python latch in `ros2/qerra_gate_node.py`. It records the first fault reason and does not overwrite it with later faults. When an unhandled exception occurs inside `_tick_callback`, the node trips the latch, publishes a zero `Twist`, and publishes `/gate/state` diagnostics containing `mode="FAULT"` and a `NODE_FAULT_LATCHED` reason.

On subsequent timer callbacks, the latched path short-circuits the normal gate evaluation, continues publishing a zero `Twist`, and retains the original fault reason. The latch cannot be cleared by `/gate/reset`. It persists for the lifetime of the process and is cleared only when a new process instance is started.

The latch is an application-level response to exceptions in the control-tick path. It is not an independent hardware safety channel. It does not protect against process termination, kernel failure, loss of power, a blocked executor that cannot run the next tick, or failure of the publisher or downstream command path. The ROS 2 node also does not make every constructor and subscription callback part of one global exception boundary.

Automatic process supervision must not be allowed to restart a faulted node and restore motion without an independent inspection and re-arm policy. A process restart resets the in-memory latch.

### 4.4 Shutdown handling

The node entry point catches `KeyboardInterrupt` and `rclpy.executors.ExternalShutdownException`. In the `finally` path it destroys the node and calls `rclpy.shutdown()` only when `rclpy.ok()` is true. The Jazzy CI workflow asserts that SIGINT results in process exit code 0.

A clean SIGINT exit is a lifecycle property. It is not evidence that a physical base has entered a safe state. The shutdown path does not establish a certified stop function, and a process that stops publishing may leave a downstream controller holding its last command, depending on that controller's command timeout and behavior. A physical system needs a separately specified and tested downstream watchdog or safety-rated stop path.

### 4.5 Flight log in the node

The node can write the same hash-chained flight log that the Webots controller writes. The log is controlled by the `flight_log_path` parameter and is disabled when the parameter is empty.

When enabled:

- `GateLogger` (`gate/gate_log.py`, schema v1) is held in `self._flight_logger`, which avoids a name collision with `rclpy.node.Node._logger`.
- Record 0 carries a manifest that embeds the gate parameters (`asdict(self._params)`) and is anchored to the genesis hash, 64 zeros.
- Each record carries `SHA256(prev_hash || canonical_bytes)`.
- `GateLogger.append()` propagates real `os.fsync()` errors to the node.
- **Requirement R-10:** if the append or the `fsync` fails, the node clamps the actuator command to zero on the current tick and feeds `log_write_failed=True` into `GateInputs`, which produces `TRIP_LOG_FAILURE`. `/gate/state` reports mode `TRIPPED`, reason `TRIP_LOG_FAILURE` and zero wheel commands in the same tick, matching `/cmd_vel_safe`.
- **Phase 1 proposal-inhibition replay:** when `proposal_invalid=True`, `gate_core._record()` writes `"proposal_invalid": True` inside `rec["inputs"]`. The field is omitted when false so historical flight-log records retain their previous input shape. `gate/gate_log.py` reconstructs the input using `proposal_invalid=bool(inputs_data.get("proposal_invalid", False))`; therefore records created before this field existed replay with the default `False`, while Phase 1 records reproduce the invalid-proposal inhibition decision. The regression `test_proposal_invalid_logged_and_replayed_bit_for_bit` verifies a 38-tick SHA-256 log spanning dwell, reset, cruise, invalid proposal, inter-tick silence and recovery through `replay_log_file()`.
- **Gate Core v0.5 measured-speed replay:** `_record()` writes `meas_left_urad_s` and `meas_right_urad_s` inside `rec["inputs"]`. `reconstruct_inputs(record)` deserializes both with `.get(...)` defaults of `None`, so logs recorded before v0.5 replay bit-for-bit with unchanged decisions. The archived Demo 10 log (section 5.1), recorded before standstill activation, replays 439/439 cycles with 0 divergence through the v0.5 replay path.
- `destroy_node()` flushes and closes the log file.
- `verify_log.py --replay` has reproduced the recorded decisions bit-for-bit in offline tests, including the Phase 1 invalid-proposal inhibition path.

Log timestamps are ROS-clock microseconds. The log records gate commands, not wheel ground truth. A hash chain is tamper-evident only against a head hash stored somewhere else, and the node does not anchor its logs.

### 4.6 Package discovery and `qerra_msgs` isolation boundary

The ROS 2 release package is the standalone `qerra_core` package. The repository retains `src/qerra_msgs` as source content, but `src/qerra_msgs/COLCON_IGNORE` masks that directory from standard `colcon` package discovery. `qerra_msgs` is not a build target in the current ROS 2 Jazzy workflow and is not declared as a dependency in `package.xml`.

The Jazzy workflow uses normal workspace discovery (`colcon list`) and builds only `qerra_core` with `colcon build --packages-select qerra_core`. It does not use the former nested `--paths` build invocation, compile the `QerraEvaluate` action IDL, or instantiate generated Goal, Result, or Feedback types. Accordingly, this brief makes no claim that `qerra_msgs` is built, installed, or interface-generated as part of the v2.4.2 `qerra_core` package baseline. The masked directory is outside the current package build and runtime dependency boundary. The `nav_msgs` dependency declared by `qerra_core` is the standard ROS message package used for `/odom`, not part of `qerra_msgs`.

### 4.7 Standard launch entry point and Pattern B topic configuration

The package installs `launch/qerra_gate.launch.py` as a standard ROS 2 launch entry point. It starts `qerra_gate_node` and exposes six topic remapping arguments:

| Launch argument | Default | Node interface remapped |
|---|---|---|
| `cmd_vel_in` | `/cmd_vel` | Gate velocity-proposal subscription |
| `cmd_vel_out` | `/cmd_vel_safe` | Gate constrained velocity publisher |
| `scan_topic` | `/scan` | Lidar subscription |
| `odom_topic` | `/odom` | Measured-odometry subscription |
| `reset_topic` | `/gate/reset` | Operator reset subscription |
| `state_topic` | `/gate/state` | Diagnostic state publisher |

For the tested Pattern B exterior arrangement, the relevant overrides are:

```bash
ros2 launch qerra_core qerra_gate.launch.py \
  cmd_vel_in:=/cmd_vel_nav \
  cmd_vel_out:=/base/cmd_vel
```

The launch file exposes all 15 node runtime parameters listed in section 4.1: `rate_hz`, `track_width_m`, `wheel_radius_m`, `robot_half_width_m`, `lidar_n_expected`, `lidar_fov_rad`, `t_react_ms`, `lidar_period_ms`, `lidar_stale_ms`, `hsr_source`, `hsr_port`, `hsr_required`, `standstill_required` (default `"false"`), `state_port`, and `flight_log_path`. Each is passed through `launch_ros.parameter_descriptions.ParameterValue` with an explicit `float`, `int`, `bool`, or `str` type rather than relying on implicit YAML type inference. Together with the six topic-remapping arguments above, the launch entry point exposes 21 configurable launch arguments.

The package manifest uses format 3 and declares direct runtime dependencies on `launch`, `launch_ros` and `nav_msgs` through `<exec_depend>` entries. The launch file is installed under `share/qerra_core/launch` through the package's `setup.py` `data_files` configuration.

The launch entry point configures topic connections; it does not authenticate publishers, prevent direct publication to the base-controller topic, or create an independent hardware stop path. The launch and remapping tests verify the tested ROS graph configuration in the Jazzy container. They do not establish actuator authority outside that graph or on a physical robot.

### 4.8 Webots supervisory controller measured-feedback path

The Webots supervisory controller `controllers/tiago_supervisory_gate/tiago_supervisory_gate.py` samples the TIAGo wheel position-sensor derivatives (`meas_left_rad_s`, `meas_right_rad_s`), converts them to integer `urad/s`, and passes them into `GateInputs` as `meas_left_urad_s` and `meas_right_urad_s`. The controller exposes the environment flag `QERRA_STANDSTILL_REQUIRED`, which defaults to `"1"` in the live Webots simulation. The Webots simulation therefore runs with standstill-qualified recovery by default, whereas `GateParams`, `QerraGateNode` and the launch file default to `False`.

These are simulated sensor derivatives from the Webots physics model, not data from physical wheel encoders. The archived Demo 7, 9 and 10 runs (section 5.1) predate activation of `standstill_required=True`; they were not re-run with the v0.5 recovery gating enabled.

---

## 5. Empirical Evidence Baseline

Evidence is reported by scope. A passing unit test, a Webots run, a ROS 2 package-startup test and a live-traffic test are different forms of evidence and are not interchangeable.

### 5.1 Webots simulation baselines

**Demo 7 — kinematic lidar stop**

| Item | Recorded value |
|---|---|
| Run ID | `RUN_1791713619` |
| Simulation | Webots R2025a, TIAGo model |
| Historical Gate version | v0.2 |
| Verified records | 1,485 continuous ticks |
| Simulation interval | 0.032 s to 47.520 s |
| SHA-256 head seal | `ae37ae62227c4fdca51233b7e4189607898ae2c27eca5bf0847414d1f0d4c191` |
| Obstacle trip clearance | 337 mm |
| Final standstill clearance | 301 mm |
| Observed coasting after trip | 36 mm |

The recorded run demonstrates the stopping-envelope trip and commanded velocity clamp in the Webots scenario. The 36 mm value is observed simulation coasting for that run; it is not a general physical braking bound.

**Demo 9 — acute distress reflex and recovery**

| Item | Recorded value |
|---|---|
| Run ID | `DEMO9_SCENARIO_B_FINAL` |
| Historical Gate version | v0.3 |
| Verified records | 438 continuous ticks |
| Simulation interval | 0.032 s to 14.016 s |
| SHA-256 head seal | `eccb0d85416cf4a651205f34f3cc0d9275bff6e2b3baa512e4b23dbef0c2714a` |
| Distress injection | t = 4.000 s, cycle 125 |
| Gate response | `TRIP_HSR_CRITICAL`; zero wheel command on the same simulation cycle boundary |
| Reset attempt during distress | t = 5.024 s; rejected as `RESET_REJECTED_HAZARD` |
| HSR stabilization | CLEAR reported at t = 8.032 s |
| Gate clear dwell completion | t = 9.056 s |

The run demonstrates the HSR-triggered clamp and guarded reset behavior under the scripted Webots inputs. The same-cycle response is a discrete simulation observation, not a real-world latency measurement.

**Demo 10 — asynchronous HSR telemetry integrity and frozen-frame recovery**

| Item | Recorded value |
|---|---|
| Run ID | `DEMO10_FROZEN_FRAME_20261120_125540` |
| Simulation | Webots R2025a, TIAGo model |
| Verified records | 439 continuous ticks |
| Simulation interval | 0.032 s to 14.048 s |
| SHA-256 head seal | `0250fdcbff64af691dc52f5d60a89305d691ce3ca6b662281e7e9c73ff46437a` |
| Gate compute latency | p50 1.07 ms, p99 2.77 ms, max 2.99 ms |
| Host wall interval (Windows 11, non-RTOS) | p50 32.0 ms, p99 53.0 ms, max 148.3 ms |
| Replay audit | 439/439 cycles reproduced bit-for-bit via `verify_log.py --replay`, compatible with Gate Core v0.5 |

The run exercises the shared pure-Python gate/hsr_receiver.py (re-exported by ros2/hsr_receiver.py) monotonic obs_id checking,frozen-frame detection, reset refusal during a fault, and controlled rebase dwell, using synthetic UDP telemetry and automated test-harness resets (`reset_origin: automated_test_harness`). The compute-latency figures measure the Gate Core evaluation on the development host; the host wall-interval figures reflect a non-real-time Windows 11 loop, and the 148.3 ms maximum shows that this loop does not provide a bounded tick interval. Neither set of figures is a latency bound for the ROS 2 deployment. The archived Demo 7, 9 and 10 runs predate v0.5 `standstill_required=True` activation (section 4.8).

The `SAFETY_CONCEPT.md` baseline records that the Demo 9 log replays bit-for-bit through Gate Core v0.4 using `verify_log.py --replay` (438 cycles). The archived Demo 9 run itself was produced with Gate v0.3; replay compatibility with v0.4 is not a new v0.4 live simulation run. Likewise, the Demo 10 replay is an offline replay of an archived log through the v0.5 replay path, in which the new measured-speed fields default to `None`; it is not a live run with `standstill_required=True`. The stream monitor (section 3.5) was not part of Demo 7 or Demo 9; Demo 10 exercises it with synthetic telemetry. The ROS 2 node, the timing profiles (section 4.2) and the node-level flight log (section 4.5) were not part of any of the three Webots runs.

### 5.2 Unit-test baseline

The counts below are the verified v2.4.2 package metadata results for the `main` baseline at commit `5734dd7`, dated 22 November 2026. The host suite was collected on the author's Windows 11 development host (Python 3.12 and 3.14) and in the Ubuntu GitHub Actions host job (`tests.yml`, Python 3.10), without ROS 2 `rclpy`; the native ROS 2 integration suite was run inside the official `ros:jazzy` container. The workflow logs and local test-run output are the authoritative records.

| Test group | Count | Evidence scope |
|---|---:|---|
| Host unit tests under `tests/` | 266 collected: 252 passed, 14 cleanly skipped without `rclpy`, 0 failures (0.837 s runtime) | v2.4.2 package metadata baseline, 22 November 2026, commit `5734dd7`; `python -m unittest discover -s tests -p "test_*.py"` |
| Native ROS 2 Jazzy container tests | 50 passing | 21 in `tests/test_gate_ros2_node.py`, 8 in `tests/test_gate_ros2_node_wiring.py`, 7 in `tests/test_gate_ros2_odom.py`, 5 in `tests/test_gate_ros2_live_traffic.py`, 4 in `tests/test_gate_ros2_dual_protocol.py`, 1 in `tests/test_gate_ros2_remapping.py`, and 4 in `tests/test_gate_ros2_nav2_exterior.py` |
| QERRA-HSR suite under `hsr/` | 20 passing (1.204 s) | Run separately by `tests.yml`; not included in the 266 tests under `tests/` |

The descriptive CI step label in `tests.yml` still displays the historical text `(211 tests)`; the executed discovery output on `5734dd7` is 266 collected tests, and the count above is taken from that output.

The 14 skipped host tests are ROS-dependent cases that cannot run on a host without `rclpy`: 5 live topic-traffic tests in `test_gate_ros2_live_traffic.py`, 4 dual-protocol and node-regression tests in `test_gate_ros2_dual_protocol.py`, 1 live topic-remapping test, and 4 live Nav2-compatible exterior tests. The two pure-Python Phase 1 regressions in `tests/test_gate_ros2_node.py` run without `rclpy`: one checks the non-finite linear/angular Twist variants (`NaN`, `+Inf`, and `-Inf`), and the other validates zero-Twist output together with `MSG_REJECTED_INVALID` in `/gate/state` JSON telemetry. The six fault-latch tests remain in the separate file `tests/test_gate_ros2_node_latch.py` and are included in the host suite; they are not a separate group in the Jazzy container count.

The Phase 1 additions include:

- **`tests/test_gate_core.py`:** 7 new tests in `TestProposalInhibition` (bringing the module to 61 tests at that milestone). They cover immediate zero-output inhibition, persistence across inter-tick silence, automatic recovery on a valid proposal, 150 ms watchdog escalation, obstacle-hazard precedence, preservation of the `TRIPPED` / `AWAITING_RESET` latch, and deterministic alternating valid/invalid handling.
- **`tests/test_gate_ros2_node.py`:** 2 new pure-Python tests, bringing the module to 21 tests. They exercise all non-finite `NaN`, positive-infinity and negative-infinity variants in linear and angular command components, and validate `(0.0, 0.0)` Twist output plus `MSG_REJECTED_INVALID` in `/gate/state` JSON telemetry.
- **`tests/test_gate_log.py`:** 1 new test, `test_proposal_invalid_logged_and_replayed_bit_for_bit`, bringing the module to 16 tests. It generates a 38-tick SHA-256 log spanning dwell, reset, cruise, `proposal_invalid=True`, inter-tick silence and recovery, then verifies bit-for-bit replay through `replay_log_file()`.

**Gate Core v0.5 and `/odom` additions:**

- **`TestStandstillDwellQualification` in `tests/test_gate_core.py` (4 new tests, bringing `test_gate_core.py` to 65 tests):** verifies dwell inhibition while the wheels turn, dwell activation after standstill, mid-dwell motion reset, and fail-closed inhibition on missing feedback when `standstill_required=True`.
- **`tests/test_gate_ros2_odom.py` (7 tests):** imports the real `ros2/qerra_gate_node.py` under a private module name with isolated ROS 2 module stubs, so it runs identically on a Windows host without `rclpy` and inside the `ros:jazzy` container, and exercises the real `_odom_callback()` and `_tick_callback()` while capturing the `GateInputs` passed to `step()`. It verifies exact integer wheel-speed conversion across straight, spin, arc, stop and reverse twists; the 100 ms freshness boundary (`100_000` us is fresh, `100_001` us is stale); rejection of `NaN`, `+Inf`, `-Inf` and malformed messages to `None`; recovery after a stale or invalid interval; and the `None` result before any message has arrived. The negative-age clock-regression branch (`odom_age_us < 0`) is implemented in `qerra_gate_node.py` but is not yet covered by a dedicated subtest in this file.
- **Workflow change:** the `ros2_jazzy.yml` lifecycle check now also asserts `node._standstill_required is False`, and the workflow executes `tests/test_gate_ros2_odom.py` inside the `ros:jazzy` container.
- **Replay support:** `gate/gate_log.py` `reconstruct_inputs()` now deserializes `meas_left_urad_s` and `meas_right_urad_s` with `None` defaults; the 439-cycle Demo 10 replay (section 5.1) verifies backward compatibility with an archived log.

**Milestones 2.1 and 2.2 — Layer 1B wire-contract and receiver-diagnostics additions:**

- **`tests/test_hsr_conformance.py` (8 tests):** standard-library `unittest` coverage for a 28,028-case float-to-permille grid sweep, threshold-constant parity, exact 0.001-grid equivalence, a 24-case rejected-payload matrix, and the NaN invalid-input asymmetry pin.
- **`tests/test_hsr_receiver_diagnostics.py` (8 tests):** standard-library `unittest` coverage using `FakeDatagramSocket` and `WindowsMessageTooLargeError` for drained/rejected counters, reset-preserved lifetime diagnostics, and bounded sanitized rejection categories.
- **Wire-fixture updates:** `tests/test_gate_ipc.py`, `tests/test_adversarial_hsr.py`, `tests/test_gate_ros2_node.py`, and `tests/test_gate_ros2_dual_protocol.py` were updated to supply the mandatory v0.4.0 wire fields. Malformed-payload tests in `tests/test_gate_ros2_node_wiring.py` intentionally continue to omit required fields so rejection behaviour remains covered.

The 50 native Jazzy tests comprise `21 + 8 + 7 + 5 + 4 + 1 + 4 = 50`. The 4 tests in `test_gate_ros2_dual_protocol.py` run with the v0.4.0 mandatory HSR wire fields; its two `TestQerraGateNodeRegressions` tests instantiate the actual node under `rclpy` and remain distinct from the pure-Python tests in `test_gate_ros2_node.py`. Counts from overlapping local and CI test groups must not be added together as if they were independent tests.

### 5.3 Continuous integration

Both GitHub Actions workflows are reported green on commit `5734dd7` on 22 November 2026. The exact run identifiers and recorded durations are listed below.

| Workflow | Run / commit evidence | Result |
|---|---|---|
| `QERRA-v2 Classical Test Suite` (`tests.yml`, Ubuntu Python 3.10) | Run #895 on commit `5734dd7` | Passed in 1 min 13 s, 22 November 2026 |
| `ROS 2 Jazzy Validation` (`ros2_jazzy.yml`, official `ros:jazzy` container) | Run #160 on commit `5734dd7` | Passed in 1 min 37 s, 22 November 2026 |

The `tests.yml` workflow runs the host supervisory-gate suite, the separate QERRA-HSR suite under `hsr/`, the license and version boundary guard, and the SEMEV-12 regression. The host discovery command is `python -m unittest discover -s tests -p "test_*.py"`; GitHub Actions runs this host job on Ubuntu with Python 3.10. The author's local Windows 11 runs use Python 3.12 and 3.14. The executed host test discovery result on `5734dd7` is 266 collected tests (252 passed, 14 skipped, 0 failures); this count is taken from the test output, not from the descriptive step-name count, which still reads `(211 tests)`.

The workflow `.github/workflows/ros2_jazzy.yml` runs in the official `ros:jazzy` container. Its checks include:

- Install build tools and dependencies, run standard workspace discovery with `colcon list`, and build only the standalone `qerra_core` package with `colcon build --packages-select qerra_core`. The masked `src/qerra_msgs` directory is ignored by `colcon` (section 4.6).
- Confirm that `qerra_gate_node` is discoverable as a package executable.
- Confirm that the installed launch file exists and inspect all declared arguments with `ros2 launch ... --show-args`.
- Start the node through `ros2 launch` with custom Pattern B remappings, capture a `/gate/state` message, and check the launch log for tick exceptions.
- Send SIGINT to the launch parent first; if it does not exit within the configured wait, escalate to SIGTERM and then SIGKILL. The workflow accepts launch exit codes 0, 130, or 143. This is a bounded shutdown check; an exit caused by SIGTERM is not itself evidence of graceful shutdown.
- Start the installed executable from a neutral working directory, capture one `/gate/state` message, check for tick exceptions, and send SIGINT.
- Instantiate `QerraGateNode` under `rclpy`, check its HSR and lidar configuration, and assert `node._standstill_required is False`.
- Run the node translator/regression and wiring tests and the `/odom` ingestion tests (`tests/test_gate_ros2_odom.py`) in the Jazzy container, followed by the live DDS topic-traffic tests (5), dual-protocol tests and node-level regressions (4), live topic-remapping test (1), and Nav2-compatible exterior tests (4) described in section 5.6.

The ROS 2 workflow assigns distinct `ROS_DOMAIN_ID` values 11 through 18 to its ROS launch, executable, initialization and test steps. It runs `pkill -9 -f "[q]erra_gate_node" 2>/dev/null || true` after the launch and standalone-executable steps to terminate any remaining gate-node child processes, then inspects the process list before the dual-protocol step for live leftover gate/launch processes. The observed PID 516 remained only as an inert `<defunct>` process after termination; it was no longer a running gate node. This cleanup and verification prevent a live child from contaminating a later DDS test step; they are CI isolation measures, not a runtime safety mechanism.

The Jazzy job sets `QERRA_REQUIRE_ROS2="1"` at job scope. Both `tests/test_gate_ros2_dual_protocol.py` and `tests/test_gate_ros2_nav2_exterior.py` explicitly enforce this setting and raise a `RuntimeError` if ROS 2 imports fail, preventing those modules from silently converting a missing `rclpy` dependency into skipped tests. This is a module-level guard for those two test modules, not a claim that every ROS-dependent test module independently enforces the setting.

The workflow exercises the node under live `/cmd_vel`, `/scan` and `/gate/reset` traffic over DDS, concurrent UDP Layer 1B reflex traffic, remapped Pattern B topics, and a Nav2-compatible exterior command-interface harness. The scenarios include Best Effort lidar streaming, clear dwell and operator reset, cruise passthrough, obstacle clamping, loss of the scan stream, loss of the proposal stream, refusal of a reset during a hazard, acute-distress injection during live cruise, loss of the UDP heartbeat, custom topic remapping, an active default-topic isolation canary, coordinated linear/angular Twist passthrough, obstacle interception, proposal-stream interruption, 10 Hz node-parameter propagation, post-reset HSR receiver continuity, and non-finite Twist command inhibition and recovery. These are evidence for the behaviours and observation windows stated in section 5.6, not a general proof of correctness.

The `/odom` path is covered by the stub-based tests in `tests/test_gate_ros2_odom.py`, which drive the real callbacks with synthetic `Odometry` messages. The live DDS scenarios listed above do not include a live `/odom` publisher.

The workflow does **not** measure end-to-end latency or timing under representative load; does not test a physical motor controller; does not build, generate, or run the `qerra_msgs` action interface; and does not exercise the node flight log under ROS. The tests run on a shared CI runner in real time, so a pass is not a timing guarantee. The workflow is evidence of standalone package construction, node initialization, launch-file discovery and execution, the listed live scenarios, selected tests, and bounded process shutdown checks, not evidence of hardware functional safety.

### 5.4 Hash-chain verification

The flight recorder uses a rolling SHA-256 chain of canonicalized records:

$$
h_i = \operatorname{SHA256}(h_{i-1} \Vert \operatorname{canonical\_bytes}_i).
$$

The anchored Demo 7, Demo 9 and Demo 10 records can be checked offline with `verify_log.py`. A hash chain provides tamper-evidence relative to a trusted anchor; it does not prove that the recorded sensors, timestamps, or physical events were truthful or correctly measured. The node's optional log (section 4.5) uses the same format and has been checked offline with `verify_log.py --replay`, with no external anchor.

### 5.5 Forged-input, fault-injection and exploit tests

The wiring test file holds 8 tests, 5 of them added for forged-input and fault-injection scenarios. The scenarios are:

| Scenario | Expected result |
|---|---|
| Reset request from a source other than `operator` (for example `proposer`) | `RESET_REJECTED_CHANNEL` |
| Reset during the clear dwell | `RESET_REJECTED_NOT_READY` |
| Reset during an obstacle breach or active distress | `RESET_REJECTED_HAZARD` |
| Malformed, non-JSON or causality-violating UDP packets | Dropped, fail-closed |
| Lidar beam count of 500 where 682 is expected | `TRIP_SENSOR_INVALID` |
| Backward jump in simulation time | `TRIP_CLOCK_ANOMALY` |
| Several hazards at once | Deterministic fail-closed result |

Seven scenarios are listed and five tests were added, so some tests cover more than one scenario. These tests show that the core refuses specific malformed or out-of-order inputs.

`tests/test_adversarial_hsr.py` holds two executable exploit scenarios, which demonstrate behaviours the current design does not prevent:

- **Masked-distress re-arm.** If an attacker silences the genuine producer, it can forge a counter regression, the 160 ms rebase, the 1.0 s clear dwell and an operator reset, and force the gate to `RUN` while the real distress condition persists.
- **Ingestion crowding.** A burst of more than 256 datagrams per tick crowds out and delays a trailing `CRITICAL` packet across ticks.

For the flood test, `tests/test_adversarial_hsr.py` requests `SO_RCVBUF = 1_048_576` on the receiving socket, guarded by `try/except OSError`, before `bind()`. This increases the test socket's receive-buffer capacity so that Linux's default `rmem_default` does not drop datagrams from the 261-packet burst before `HsrReceiver` can drain them. It makes the test exercise the application-level bounded-drain behaviour rather than prematurely measuring kernel receive-buffer drops; it is a test-harness setting, not a production receiver mitigation.

These are demonstrations of residual risk, not evidence of protection (section 6.6). No exploit test covers forged `/odom` input; a forged standstill report is an unmitigated case of the trust-boundary assumption in section 1.5.

### 5.6 Live topic traffic, dual-protocol, remapping and Nav2-compatible exterior tests

The native ROS 2 integration tests run in the `ros:jazzy` container. The DDS integration harness drives the node through real topics (`/cmd_vel`, `/scan` with Best Effort sensor-data QoS, `/gate/reset`) and observes `/cmd_vel_safe` and `/gate/state`. ROS-dependent modules skip on hosts without `rclpy`; the dual-protocol and Nav2 exterior modules additionally fail loudly in CI when `QERRA_REQUIRE_ROS2="1"` is set but ROS 2 imports fail.

**`tests/test_gate_ros2_node.py` (21 tests), translator, helper and pure-Python regression coverage:**

The module contains 17 original translator/kinematics, lidar, receiver and node-helper tests plus four pure-Python regressions that run without `rclpy`:

1. `test_10hz_dt_us_scales_max_tick_gap_and_allows_dwell_recovery` verifies that `get_live_gate_params(dt_us=100_000)` derives `max_tick_gap_us=200_000` and allows the 1.0 s continuous-clear dwell to complete across 100 ms ticks with a consistent 10 Hz lidar/staleness profile.
2. `test_hsr_receiver_post_reset_continuity_across_40ms_and_50ms_phases` uses `HsrReceiver` and `step()` to sweep every 1 ms phase offset of 40 ms (25 Hz) and 50 ms (20 Hz) UDP streams relative to the 32 ms gate tick, verifying that the preserved receiver state does not produce a spurious `TRIP_HSR_INVALID` after `RESET_ACCEPTED`.
3. The Phase 1 non-finite Twist test exercises `NaN`, `+Inf`, and `-Inf` in both `linear.x` and `angular.z`, verifying that the translator rejects each non-finite variant rather than creating a wheel-speed proposal.
4. The Phase 1 diagnostic test validates a `(0.0, 0.0)` Twist together with `MSG_REJECTED_INVALID` in `/gate/state` JSON telemetry for the invalid-proposal inhibition path.

**`tests/test_gate_ros2_odom.py` (7 tests), `/odom` ingestion and freshness watchdog with isolated ROS 2 stubs:**

The file loads the real `ros2/qerra_gate_node.py` under a private module name with stub `rclpy`, `geometry_msgs`, `nav_msgs`, `sensor_msgs` and `std_msgs` modules that are removed from `sys.modules` after import. The real `QerraGateNode._odom_callback()` and `_tick_callback()` therefore execute without a ROS 2 installation and without sockets (the state sender and `send_state` are patched out), and a spy on `step()` captures each `GateInputs`. Its seven tests are: the 100 ms ceiling constant; `None` measured speeds before any `/odom` message; exact integer wheel-speed conversion for straight, spin, arc, stop and reverse twists; the freshness boundary (ages of 0, 32,000 and 100,000 us are fresh, 100,001 and 500,000 us are `None`); `NaN`, `+Inf` and `-Inf` in either twist component reset both values to `None` even when the message is fresh; a malformed message resets both values to `None` without latching a node fault; and recovery to valid values after a stale interval and after an invalid message. What these tests do not show: the negative-age branch (`odom_age_us < 0`) has no dedicated subtest, no live DDS `/odom` publisher is involved, and the stubs do not exercise `rclpy` subscription or QoS behaviour for `/odom`.

**`tests/test_gate_ros2_live_traffic.py` (5 tests), HSR disabled so that Layer 1A is isolated:**

1. A clear corridor produces the 1.0 s dwell and `AWAITING_RESET`; an operator reset enters `RUN`; `/cmd_vel_safe` passes the proposal through; an obstacle breach trips `TRIP_OBSTACLE` and clamps `/cmd_vel_safe` to zero.
2. Silencing `/scan` produces `TRIP_SENSOR_INVALID` once the scan-freshness limit is exceeded.
3. An operator reset while an obstacle is present is refused (`RESET_REJECTED_HAZARD`, reported in the `events` list).
4. Silencing `/cmd_vel` produces `TRIP_PROPOSER_STALE` once the 150 ms proposal limit is exceeded.
5. `test_live_topic_traffic_non_finite_twist_inhibition_and_recovery` establishes `Mode.RUN` cruise, injects a single `NaN` Twist, and verifies that the next Gate evaluation publishes `(0.0, 0.0)` on `/cmd_vel_safe` while remaining in `Mode.RUN` and emitting `MSG_REJECTED_INVALID`. A subsequent valid Twist restores cruise automatically without an operator reset. Continuous `+Inf` / `-Inf` Twists do not refresh the held proposal timestamp; zero output remains inhibited and the 150 ms proposer watchdog eventually escalates to `TRIP_PROPOSER_STALE`. `TrafficHarnessNode` captures observed events in a thread-safe `seen_events` set so live assertions do not depend on a narrow inter-tick observation window.

**`tests/test_gate_ros2_dual_protocol.py` (4 tests total), `hsr_required=true` and `hsr_source=udp` on port 5008 alongside live DDS traffic:**

The module contains two live dual-protocol tests and a `TestQerraGateNodeRegressions` class with two additional node-level tests that instantiate `QerraGateNode` under `rclpy`:

1. The dual-dwell clear recovery completes; then a `CRITICAL` UDP packet injected during live DDS cruise trips `TRIP_HSR_CRITICAL` and clamps `/cmd_vel_safe` to zero.
2. Cutting the UDP stream while the DDS topics stay active trips `TRIP_HSR_STALE` and clamps `/cmd_vel_safe` to zero.
3. `test_node_10hz_dt_us_parameter_propagation` launches the node with `rate_hz=10.0`, `lidar_period_ms=100.0`, `lidar_stale_ms=300.0`, and `t_react_ms=160.0`, then verifies `_dt_us=100_000`, `_params.dt_us=100_000`, and `_params.max_tick_gap_us=200_000`.
4. `test_node_accepted_reset_preserves_hsr_receiver_state` exercises the actual node tick path and verifies that an accepted reset does not wipe the receiver state, preventing a false `TRIP_HSR_INVALID` on the following `RUN` tick.

What these tests show: that, for these scenarios, the Layer 1A inputs (DDS) and the Layer 1B input (UDP) combine as designed in a real ROS 2 Jazzy environment, and that the scan subscription interoperates with a Best Effort publisher. The Phase 1 live test additionally demonstrates the tested software behaviour for one invalid Twist, subsequent valid-command recovery, and persistent invalid input reaching the proposer watchdog. What these tests do not show: physical stopping time or distance after zero publication, timing bounds (the harness runs in real time on a shared runner), behaviour under representative CPU or I/O load, behaviour with a physical lidar driver, or any hostile-publisher scenario beyond section 5.5.

**`tests/test_gate_ros2_remapping.py` (1 test), Pattern B topic remapping:**

1. Applies node-specific remappings so the gate receives proposals on `/cmd_vel_nav`, receives scans on `/front_lidar/scan`, and publishes its constrained command to `/base/cmd_vel`.
2. Checks forward cruise and obstacle clamping through the remapped command path.
3. Publishes to the unmapped default `/cmd_vel` and checks that it does not satisfy the gate's remapped proposal input; checks that the default `/cmd_vel_safe` subscriber receives no messages during the asserted phase.

This is a single live remapping test. It verifies the specific topics and scenario configured by the harness; it does not enforce publisher identity or exclusive base-controller authority.

**`tests/test_gate_ros2_nav2_exterior.py` (4 tests), Nav2-compatible exterior command-interface integration:**

The file uses a ROS 2 harness that simulates an external proposer and a base-controller subscriber. It does not start or exercise an actual Nav2 `controller_server`, Nav2 lifecycle manager, controller plugin, or navigation action. The term *Nav2-compatible* describes the external command-interface pattern, not a complete Nav2 stack integration.

1. **Linear cruise and active default-topic isolation canary.** The harness establishes cruise through `/cmd_vel_nav` to `/base/cmd_vel`. It then stops the remapped proposal feed and publishes five distinct `0.35 m/s` proposals exclusively on the unmapped default `/cmd_vel`, while keeping scans active. The test asserts that the default `/cmd_vel_safe` subscriber receives zero messages and, if a base-command message is present, that the latest observed `/base/cmd_vel` value is not the injected `0.35 m/s` proposal. This is a bounded canary check over the test observation window, not a proof against every possible ROS graph bypass or publisher.
2. **Coordinated arc passthrough.** A body-twist proposal (`linear.x = 0.15 m/s`, `angular.z = 0.10 rad/s`) is sent on `/cmd_vel_nav` and the corresponding body-twist values are checked on `/base/cmd_vel`. This exterior test checks Twist-level passthrough. It does not itself measure wheel speeds or independently verify physical differential-drive kinematics; the separate translator tests in `test_gate_ros2_node.py` exercise the software Twist-to-wheel and wheel-to-Twist conversion functions.
3. **Dynamic obstacle interception.** The harness continues proposing motion while publishing an obstacle scan. The test waits for `TRIPPED`, reason `TRIP_OBSTACLE`, and zero linear and angular output on `/base/cmd_vel`. The test uses a bounded polling deadline (2 seconds); it does not measure or establish a 32 ms end-to-end response bound.
4. **Proposal-stream interruption watchdog.** After establishing active cruise, the harness stops publishing velocity proposals while continuing to publish fresh scans. The test waits for `TRIP_PROPOSER_STALE` and zero output on `/base/cmd_vel`. The configured proposer freshness threshold is 150 ms, but the test's polling deadline (3 seconds) is not a measurement of the exact trip latency or a WCET bound.

The 4 Nav2-compatible exterior tests therefore establish selected DDS topic-level behaviours under a simulated proposer/base interface. They do not demonstrate an actual Nav2 controller, a physical base controller, wheel-side motion, differential-drive response on hardware, or exclusive authority over the base command interface.

## 6. Epistemic Limits and Safety Honesty Boundaries

The following limits define what can and cannot be concluded from the current evidence.

### 6.1 Simulation and hardware boundary

The gate has been evaluated in Webots R2025a, and the ROS 2 package has been built, started and exercised under live traffic in Linux CI. No physical robot, physical laser scanner, motor driver, brake, or hardware emergency-stop interface has been tested as part of the stated baseline. There are no measured wheel-slip, payload, surface-friction, gradient, or battery-state distributions.

### 6.2 Reaction-time model and scan freshness

The reaction-time allowance is now a parameter with two documented profiles (section 4.2), but no value in either profile has been measured. The 32 ms figure came from one Webots discrete control step. The ROS 2 defaults come from an engineering estimate of the chain (scan period, transport, gate evaluation, scheduling jitter, actuator response), and general-purpose Ubuntu Linux and `rclpy` do not provide a hard real-time deadline guarantee.

Two specific limits follow from the numbers in section 4.2:

- **The profile values are not upper bounds.** The simulation default (96 ms) lies inside the estimated 86 to 98 ms range, and the hardware value (160 ms) lies inside the estimated 154 to 166 ms range. A real chain could exceed either figure. The transport, jitter and actuator terms are estimates.
- **The freshness limit is looser than the reaction budget assumes.** The budget counts one scan period of sensing delay. The freshness limits (96 ms and 300 ms) are three scan periods, so the gate accepts a scan up to two periods older than the budget assumes: 64 ms in simulation and 200 ms on hardware. At 196 mm/s that is about 13 mm and 39 mm of travel that the envelope does not include. The startup invariant guards against a limit that is too tight, not one that is too loose.

A physical reaction-time budget must also include, at minimum:

- Scanner acquisition and publication timing, with phase and device-specific behaviour measured.
- Sensor driver and operating-system scheduling delays.
- DDS transport, middleware queues, and executor dispatch.
- Gate evaluation and publication delays.
- Base-controller reception and update timing.
- Motor-driver ramp-down and the measured mechanical deceleration response.

The envelope remains an estimate until the complete chain has been instrumented and the stopping envelope recalculated from measured latency and deceleration bounds.

### 6.3 Commanded speed versus measured motion

Gate Core v0.5 changed one thing and left several limits unchanged.

**What v0.5 changed.** The recovery calm dwell in `Mode.TRIPPED` can now be gated on measured wheel speeds (`standstill_required=True`), so that the 1.0 s dwell cannot elapse while the platform is still moving (section 3.4). This changes recovery timing only; the gate still commands `(0, 0)` immediately on any trip, and it does not generate a braking profile (section 3.4, architectural decision).

**What remains unchanged.**

1. **The stopping envelope still uses commanded velocity.** `d_stop_mm()` computes the dynamic stopping envelope from the **commanded** reference speed, `max(last_cmd, clamped)`, not from measured wheel velocity. If the robot is still moving because of inertia, slip, slope, or a delayed controller response while the commanded velocity has already fallen, the calculated stopping envelope may be smaller than the distance required to stop the physical platform. Measured speeds feed only the recovery-dwell predicate.
2. **Standstill qualification is opt-in.** `standstill_required` defaults to `False` in `GateParams`, in `QerraGateNode`, and in `launch/qerra_gate.launch.py`. Outside the Webots controller (where `QERRA_STANDSTILL_REQUIRED` defaults to `"1"` in the live simulation, section 4.8), recovery follows the v0.4 timing behaviour unless the parameter is explicitly enabled.
3. **`/odom` verifies physical standstill only when it is backed by real feedback.** ROS 2 `/odom` reflects physical motion only when it is derived from closed-loop wheel encoders or state estimation (`open_loop=false` in `diff_drive_controller`). Under `open_loop=true`, or with four wheels locked while the platform skids, `/odom` does not verify physical standstill and the qualification can pass while the platform moves. In addition, the node derives wheel speeds from the body twist (`linear.x`, `angular.z`) through the same ideal differential-drive model used for command translation; it does not read individual wheel encoders, so per-wheel slip is not observable.
4. **The tolerance is unvalidated.** `w_standstill_tol_urad_s = 50,000` (0.05 rad/s, approximately 4.9 mm/s on 98 mm wheels) has not been validated against physical hardware, encoder noise, or odometry drift.

A validated deceleration model and a measured-motion input to the stopping envelope itself are still necessary before the envelope can support physical safety claims.

### 6.4 Geometric and sensor coverage limits

The corridor filter approximates a straight forward swept corridor. It does not model the robot's full rotating footprint, the swept path of a pivot or curved turn, or rearward motion. Under AR-2 Option A, with `w_min_urad_s=0`, if either wheel proposal requests reverse rotation, both wheel outputs clamp symmetrically to `(0, 0)`. Differential center pivots and reverse maneuvers are therefore halted rather than executed without rearward coverage. This clamp is not proof that the robot is safe during every permitted forward differential-drive maneuver; curved forward arcs still require swept-volume coverage.

The ROS 2 adapter checks scan length but does not verify all `LaserScan` angular metadata or the sensor-to-base transform. The raw minimum-return check can be satisfied by lateral returns even when the forward sector is occluded. These limits require sensor-specific validation and improved geometric coverage checks.

### 6.5 Proposer freshness, measurement freshness and command provenance

The pure core can validate an explicit proposal timestamp. In the ROS 2 wrapper, however, the adapter assigns the current node time when a `Twist` callback receives a message. Since `geometry_msgs/msg/Twist` has no source timestamp or publisher identity, the 150 ms watchdog does not prove the age of the planner's original command. DDS queueing can also delay callback processing.

**`/odom` uses callback receipt time.** The measured-odometry path has the same property. `_odom_callback()` stamps `_odom_stamp_us` with `_get_ros_time_us()` when the message is received; it does not use `Odometry.header.stamp` or the encoder capture time. The 100 ms freshness watchdog (`DEFAULT_ODOM_STALE_US = 100_000` us) therefore bounds the time since callback receipt, not the age of the underlying measurement, and DDS queueing or a slow upstream estimator can make a measurement older than the watchdog implies. The backward-clock-jump branch (`odom_age_us < 0`) fails closed to `None`, but it is not covered by a dedicated subtest (section 5.2).

**Mitigated non-finite Twist proposals (NaN/Inf):** `twist_to_proposal()` rejects non-finite `linear.x` or `angular.z` values by raising `ValueError`. `_cmd_vel_callback()` catches the exception, sets `self._latest_proposal = None`, and sets `self._proposal_invalid = True`; a subsequent valid finite Twist stores a proposal and resets the adapter flag to `False`. `_tick_callback()` transfers the invalid indication to `GateInputs.proposal_invalid`. On the Gate Core tick that processes it, the core emits `MSG_REJECTED_INVALID`, sets `GateState.proposal_inhibited=True`, and commands `(0, 0)` while remaining in `Mode.RUN`. The previously held proposal's `sim_stamp_us` is not refreshed. Inhibition persists across inter-tick silence until a fresh valid finite proposal clears it or the existing 150 ms proposer freshness watchdog expires and escalates to `TRIP_PROPOSER_STALE`. Higher-priority obstacle and required-HSR trips take precedence, and invalid input does not clear an existing `TRIPPED` or `AWAITING_RESET` recovery latch.

The Phase 1 tests verify the specified software behaviour, including a single invalid input followed by automatic recovery, and continuous `+Inf` / `-Inf` input that does not refresh the held proposal timestamp and eventually reaches the watchdog. The following boundaries remain:

1. **Software setpoint is not physical stopping:** outputting `(0, 0)` is a command published by the node, not an instantaneous stop of the robot. Actual deceleration depends on the downstream controller, motors, mechanics, payload, surface and other physical conditions; none has been validated on hardware here.
2. **Rapid valid/invalid chattering is not debounced:** a sequence such as `VALID -> NaN -> VALID -> NaN` can refresh `held.sim_stamp_us` on each valid frame. The watchdog may therefore remain satisfied while the software output alternates between the valid commanded speed and zero during invalid intervals. The current Phase 1 behaviour does not impose a separate invalid-rate or chattering threshold, nor does it latch the first invalid sample.
3. **No source timestamp in `Twist`:** `geometry_msgs/msg/Twist` still has no header timestamp or publisher identity. The adapter uses callback receipt time rather than the planner's original command-generation time, so the 150 ms watchdog is not an end-to-end planner-age guarantee.

A deployment should use a stamped proposal interface, define a clock-domain policy, validate source identity and sequence progression, and test queue behavior under congestion and replay. Any future chattering/debounce policy must define its timing and recovery semantics explicitly and be regression-tested; it must not silently change the meaning of the existing 150 ms watchdog. A deployment that enables `standstill_required` should likewise consume the odometry header stamp or encoder capture time rather than callback receipt time.

### 6.6 Authentication, trust boundary and forged-input sequences

The `/gate/reset` topic accepts the string `operator` but does not authenticate the publisher. The UDP HSR receiver and the operator-reset socket are bound to the local host, but they provide no sender authentication, integrity code or replay protection. The node does not configure SROS2 governance and permission policies. Absolute topic names also require deliberate namespace and remapping design for multi-robot deployments. Authentication, authorization, anti-replay measures, network isolation, and process privilege separation remain deployment requirements. The `/odom` subscription is likewise unauthenticated: a publisher able to send forged odometry could report standstill during motion and satisfy the qualification when it is enabled.

The single most serious sequence this design does not defend against is a **masked-distress re-arm**, by a hostile process that can send to the localhost ports:

1. After a real trip, it sends a counter regression, which starts the rebase dwell.
2. It sends well-formed, fresh `CLEAR` frames with plausible timestamps, long enough to satisfy the rebase and the gate's own dwell.
3. Once the gate reaches `AWAITING_RESET`, it sends `operator`.

The gate would then return to `RUN` while a real distress condition persists, and the human confirmation that the HSR recovery contract relies on would have been replaced by a forged datagram. The robot would still be limited to the stopping envelope and subject to every other trip. By design the sequence needs the real producer to be silent or dead, because an interleaved real producer shows up as counter regressions, which fail closed. An executable test in `tests/test_adversarial_hsr.py` demonstrates this behaviour (section 5.5). Forged `CRITICAL` datagrams are a nuisance-trip and availability problem, not a safety problem, because a forged stop is a stop.

Other unauthenticated-channel concerns:

- A flood of valid-looking datagrams can exceed the bounded drain (256 datagrams per tick) and delay or crowd out a real `CRITICAL` packet. The second executable exploit test demonstrates this (section 5.5).
- On Windows, a socket bound without exclusive-address semantics may be hijackable by another process. Check this for the socket options in use. This is not exercised by a test.
- A local process can compute plausible timestamps from the system clock or from the clock echo.

Mitigation belongs at the operating-system and ROS-graph layer (section 1.5). If application-level authentication is added later, the minimal stdlib pattern is a keyed MAC (HMAC-SHA256) over a session identifier, a strictly increasing sequence number, a per-run nonce and the payload, with separate keys for the telemetry producer and the operator tool. A shared key readable by the gate is also readable by any process running as the same user, so it does not protect against that attacker.

### 6.7 Process failure, logging and the software setpoint boundary

A zero `Twist` is a software command. It does not remove drive power, apply a certified mechanical brake, or invoke hardware STO. A Python process cannot guarantee that it will publish a zero command after abrupt termination, a kernel failure, a process crash outside the handled tick path, or a loss of communication.

A physical design would require an independent downstream command timeout or hardware watchdog and a safety-rated stop path appropriate to the target platform. The application-level node fault latch is not a substitute for those mechanisms.

When the flight log is enabled, `append()` and `os.fsync()` run inside the control tick. A failure trips the gate (requirement R-10), but a slow disk does not raise an error; it delays the tick. The latency of this write under ROS has not been measured. The log is disabled by default.

**Executor and callback-serialization assumption:** `QerraGateNode` is currently run through `rclpy.spin(node)`, which uses a `SingleThreadedExecutor` by default and serializes subscription and timer callbacks without mutex locks. The node's shared mutable callback state includes `_latest_proposal`, `_latest_ranges`, `_reset_requested`, and the measured-odometry state `_meas_left_urad_s`, `_meas_right_urad_s` and `_odom_stamp_us`, all of which are part of this executor-serialized callback state. ROS 2 entities created without an explicit callback group are assigned to the node's default `MutuallyExclusiveCallbackGroup`; therefore, simply substituting a `MultiThreadedExecutor` does not by itself introduce parallel callback execution while all relevant callbacks remain in that same default group. A concurrency risk arises if future changes assign callbacks accessing this shared state to different callback groups or to a `ReentrantCallbackGroup`; such a change requires an explicit mutual-exclusion or synchronization design and corresponding tests. Because `_odom_callback()` writes the left and right measured values and the stamp as separate assignments, a non-serialized executor could expose a tick to a partially updated measurement.

### 6.8 Timing and formal assurance boundary

The project has deterministic core logic and automated tests. The current evidence does not include a formal proof of the gate's safety invariants, model checking of all state transitions, worst-case execution-time analysis, or statistical reaction-time distributions. A 31.25 Hz timer configuration is not a WCET result.

### 6.9 Perception stream monitor limits

The stream monitor (section 3.5) detects counter faults. It does not detect a frozen sensor behind a live producer: a producer that republishes the same camera frame with a fresh counter and fresh timestamps passes every check. Stamps are supplied by the producer, and the synthetic producer stamps from the clock echo, not from sensor capture, so the freshness checks measure the producer loop, not the sensor. The monitor protects only when `hsr_required` is true. The separate HSR freshness contract remains `t_hsr_stale_us = 96,000 us` (96 ms): a nominal 10 Hz producer with a 100 ms period exceeds that ceiling and triggers `TRIP_HSR_STALE`. A nominal producer rate of at least 20 Hz (period no greater than 50 ms) is the practical minimum recommended to leave jitter margin under the default threshold. This is not a guarantee of end-to-end sensor freshness or physical latency; actual capture-to-gate age must be measured.

**ODD placeholders and perception non-claim:** The HSR activation thresholds (`0.45` / `0.75` normalized distress score, mapped to `450` / `750` permille) and `ISOLATION_COUNT_THRESHOLD = 1` are author-chosen engineering placeholders; they have not been validated against any human population, posture, gait, or sensor data. Operational Design Domain (ODD) profiles are configuration slots; only the default profile is exercised in simulation and CI. The current wire contract carries no metric person-distance measurement. No claim is made about real-distress detection performance, false-alarm rate, or miss rate.

**Contradictory-frame and black-channel scope:** Under the intended black-channel-style treatment of the UDP telemetry path (an informative EN 50159 design analogy, not a claim of EN 50159 conformity), contradictory or invalid datagrams rejected by the parser—such as `state_mismatch` or timestamp-causality failures—are dropped before they enter `step_hsr_stream()`, counted in `hsr_rejected_total`, and represented by fixed sanitized rejection categories. Such a rejected datagram does not by itself immediately produce `TRIP_HSR_INVALID`. If a live producer interleaves valid `CLEAR` frames with rejected contradictory frames, the last accepted `CLEAR` status remains held and refreshed by those valid frames; if valid frames then stop, the held status ages until the 96 ms HSR freshness watchdog trips `TRIP_HSR_STALE`. This distinguishes parser-level rejection diagnostics from stream-monitor faults such as repeated or regressing `obs_id`, which can make the receiver return `(None, None)` and trigger `TRIP_HSR_INVALID` when HSR is required.

### 6.10 Standards boundary

ISO 13849-1, ISO 13482, ISO 3691-4 and EN 50159 are informative design references in this research prototype. No clause-by-clause conformity assessment, risk-reduction validation, Performance Level calculation, Safety Integrity Level calculation, certification, or approval is claimed.

---

## 7. Concrete Research Collaboration Vectors

The following are defined engineering work packages. Each requires evidence beyond the current simulation and CI baseline.

### Vector 1 — End-to-end reaction-time measurement

**Objective:** Replace the estimated reaction allowance and scan-freshness limit with measured timing data for a complete ROS 2 and actuator chain.

**Research question:** What are the observed minimum, median, p95, p99, maximum, and experimentally justified upper bounds from scanner acquisition to gate trip, safe-command publication, base-controller reception, and measured wheel deceleration? How should the scan-freshness limit relate to the reaction budget?

**Required work:** Instrument acquisition timestamps, ROS callback dispatch, timer start and completion, publication, controller reception, and wheel feedback. Record clock synchronization error and load conditions. Report distributions by sensor rate, executor configuration, CPU load, DDS configuration, and network topology. Include the cost of the optional flight-log write. Re-derive `t_react`, `lidar_stale_ms` and `d_stop` from the measured chain.

### Vector 2 — Hardware stopping-distance characterization

**Objective:** Establish whether the 0.5 m/s^2 design deceleration and 300 mm margin are appropriate for a defined platform envelope.

**Research question:** How do payload, floor material, gradient, wheel wear, battery state, caster behavior, and commanded turning rate affect physical stopping distance?

**Required work:** Conduct instrumented, repeatable stops at controlled speeds and payloads. Compare commanded wheel speed with encoder-derived and independently measured platform velocity. Derive conservative deceleration bounds and quantify run-to-run variation. No stopping claim should be generalized beyond the tested configuration. Include the standstill-qualification path: characterize how faithfully `/odom` or encoder feedback reports physical standstill under slip and under `open_loop=true` configurations, and validate or re-derive `w_standstill_tol_urad_s` against measured encoder noise and drift.

### Vector 3 — ROS 2 actuator authority, authentication and security topology

**Objective:** Make the gate's authority boundary enforceable rather than conventional, and decide which local-process threats are in scope.

**Research question:** Which combination of command remapping, namespace isolation, DDS permissions, process privileges, socket access control and base-controller configuration prevents any untrusted publisher from bypassing the gate, issuing an unauthorized reset, or injecting forged telemetry?

**Required work:** Define the complete ROS graph, demonstrate that the base controller accepts only the gate output, and test unauthorized publisher attempts. Extend the existing exploit tests (masked-distress re-arm, ingestion crowding) to the proposed mitigations, add socket hijack, and show which scenarios each mitigation closes. Validate reset authorization, and verify behavior after gate process death and communication loss. Include multi-robot namespace and domain-isolation tests.

### Vector 4 — Formal state-machine verification

**Objective:** Specify the Gate Core transition system and check recovery and fail-closed properties independently of implementation tests.

**Research question:** Under what assumptions can the system guarantee that a trip cannot transition to motion without continuous-clear dwell, valid HSR status when required, and an accepted operator reset?

**Required work:** Define invariants, transition guards, clock assumptions, reset semantics, and fault states. Model-check the state machine, including the rebase dwell of the stream monitor, examine simultaneous and reordered events, and generate implementation-level tests from the formal model. Explicitly distinguish properties of the mathematical core from properties of the ROS 2 executor and communications shell.

### Vector 5 — Lidar geometry and motion-envelope coverage

**Objective:** Extend the current straight corridor approximation to a validated robot footprint and motion-dependent swept volume.

**Research question:** How should the gate evaluate obstacle clearance during rotation, curved paths, reverse motion, and transitions between translation and rotation?

**Required work:** Validate scanner metadata and extrinsic transforms; derive a footprint-aware swept region; evaluate occlusion and sparse-return cases; and compare the present corridor filter against polygonal or trajectory-based collision monitors. Include explicit tests for blind forward sectors with valid lateral returns.

### Vector 6 — HSR input calibration and human-context validation

**Objective:** Establish the operational characteristics of the three HSR vectors using defined input sources and documented error rates.

**Research question:** What false-positive, false-negative, detection-delay, and recovery characteristics result when distress, isolation, and environmental-proximity signals are derived from real perception systems rather than injected simulation values? How can freshness be tied to sensor capture and not to the producer loop?

**Required work:** Define sensor provenance, confidence calibration, temporal filtering, input-quality indicators, and uncertainty handling. Evaluate the effect of missed, delayed, contradictory, and corrupted signals. Keep HSR as an assistive contextual reflex; do not treat its current threshold logic as validated human-state perception.

---

## 8. Conclusion

QERRA-v2 Classical provides an inspectable deterministic gate core, a ROS 2 Jazzy node wrapper, a forward lidar corridor filter, an HSR telemetry input with a sequence-checking stream monitor, a latched recovery contract with optional standstill qualification, node-level fault handling, rate-parameterized timing profiles, Phase 1 non-finite Twist command inhibition, the Layer 1B v0.4.0 mandatory wire contract and HSR receiver rejection diagnostics from Milestones 2.1 and 2.2, and an optional hash-chained flight log with backward-compatible deterministic replay of the new inhibition and measured-speed inputs. The core's separation from ROS 2, explicit state inputs, integer decision units, and reproducible simulation logs provide a concrete basis for further systems-engineering evaluation.

The present evidence supports the following statements:

- The Gate Core v0.5 is implemented as a deterministic pure-function component and is covered by unit tests, including seven Phase 1 proposal-inhibition regressions and four `TestStandstillDwellQualification` regressions in `tests/test_gate_core.py` (65 tests in the module).
- Gate Core v0.5 resolves the "Standstill Dwell Trap" by gating the recovery calm dwell on measured wheel speed when `standstill_required=True`: the dwell starts only after confirmed standstill, resets to zero if motion resumes, and fails closed on missing feedback. Generating a deceleration ramp (`TRIP_BRAKING`) inside the Gate was evaluated and rejected so that the gate remains a Checker that commands `(0, 0)` immediately on any trip.
- The ROS 2 node subscribes to `/odom`, converts the measured body twist to integer wheel speeds, and resets them to `None` on stale (older than 100 ms), clock-regressed, non-finite or malformed input. `tests/test_gate_ros2_odom.py` (7 tests) exercises the real callbacks under isolated ROS 2 stubs on Windows and in the Jazzy container.
- The supervisory gate and HSR reflex behavior have been demonstrated in the specified Webots scenarios, including Demo 10 (439 continuous ticks, SHA-256 head seal `0250fdcbff64af691dc52f5d60a89305d691ce3ca6b662281e7e9c73ff46437a`, replayed 439/439 bit-for-bit through the v0.5 replay path). The archived Demo 7, 9 and 10 runs predate `standstill_required=True` activation.
- The standalone `qerra_core` ROS 2 package builds and starts under ROS 2 Jazzy in GitHub Actions. The `src/qerra_msgs` directory is masked by `COLCON_IGNORE`, excluded from `colcon` discovery/build, and absent from `package.xml` runtime dependencies; no `qerra_msgs` action interface generation is part of this baseline.
- The verified host test baseline at commit `5734dd7` (22 November 2026) is 266 collected tests under `tests/`: 252 passed, 14 cleanly skipped on hosts without `rclpy`, and 0 failures. This includes the standard-library `unittest` suites `tests/test_hsr_conformance.py` (8 tests, including the 28,028-case float-to-permille grid sweep and 24-case rejected-payload matrix) and `tests/test_hsr_receiver_diagnostics.py` (8 tests for lifetime counters and sanitized rejection diagnostics). The QERRA-HSR suite under `hsr/` contributes 20 separately passing tests.
- Milestones 2.1 and 2.2 make `hazard_proximity` and `persons_nearby_count` mandatory in the Layer 1B v0.4.0 wire parser and add monotonic receiver diagnostics: `packets_drained_total`, `packets_rejected_total`, and `last_rejection_reason` persist across receiver reset; rejection reasons are fixed sanitized categories capped at 64 characters. The node publishes `hsr_rejected_total` and `hsr_last_rejection_reason` in `/gate/state`.
- The verified native Jazzy baseline is 50 passing tests: 21 translator/helper and pure-Python regression tests, 8 wiring/parameter/fault-injection tests, 7 `/odom` ingestion and watchdog tests, 5 live DDS topic-traffic tests, 4 dual-protocol and node-level regression tests using the v0.4.0 mandatory fields, 1 topic-remapping test, and 4 Nav2-compatible exterior command-interface tests.
- The Phase 1 proposal-inhibition tests verify that a non-finite Twist produces `(0, 0)` on the Gate evaluation tick while the mode remains `RUN`, emits `MSG_REJECTED_INVALID`, remains inhibited across inter-tick silence without refreshing the held proposal timestamp, recovers automatically on a fresh valid proposal, and escalates through `TRIP_PROPOSER_STALE` if valid input does not return before the 150 ms freshness limit. The live DDS test checks the corresponding ROS topic behaviour.
- The flight-log regression `test_proposal_invalid_logged_and_replayed_bit_for_bit` verifies a 38-tick SHA-256 log containing invalid-proposal inhibition, inter-tick silence and recovery. `reconstruct_inputs()` defaults the absent `proposal_invalid`, `meas_left_urad_s` and `meas_right_urad_s` fields to `False`, `None` and `None` respectively, preserving replay compatibility with historical records that predate Phase 1 and v0.5.
- The 10 Hz regression coverage verifies that `rate_hz=10.0` propagates `dt_us=100,000` into `get_live_gate_params()` and sets `max_tick_gap_us=200,000`; separate tests cover HSR receiver continuity after `RESET_ACCEPTED` across 40 ms and 50 ms UDP producer periods, including all 1 ms phase offsets, and the actual `QerraGateNode` reset path.
- The standard launch file `launch/qerra_gate.launch.py` exposes 15 explicitly typed node parameters (including `standstill_required`, default `"false"`) and six configurable topic-remapping arguments (including `odom_topic`, default `/odom`), 21 launch arguments in total; `package.xml` declares direct runtime dependencies on `launch`, `launch_ros` and `nav_msgs`.
- The ROS 2 Jazzy workflow uses distinct `ROS_DOMAIN_ID` values 11 through 18 for ROS steps, performs gate-process cleanup after launch/executable checks, and inspects for leftover processes before the dual-protocol stage. The lifecycle check asserts `node._standstill_required is False`. The dual-protocol and Nav2 exterior test modules enforce `QERRA_REQUIRE_ROS2="1"` so missing ROS 2 imports fail rather than silently skip those modules.
- The Pattern B tests exercise a Nav2-compatible external command interface using `/cmd_vel_nav` and `/base/cmd_vel`, including an active default-topic isolation canary. They do not instantiate an actual Nav2 stack or establish exclusive actuator authority.
- The node publishes diagnostic state, including secondary gate events, final clamped wheel commands, the `standstill_required` configuration flag, HSR rejection totals and sanitized rejection categories, HSR frozen/rebase state, and the process-lifetime tick fault latch; it also handles the tested SIGINT lifecycle and bounded launch-shutdown procedure.
- The core refuses the specific forged and malformed inputs listed in section 5.5, and two executable exploit tests demonstrate what it does not prevent. The flood test configures a larger receive buffer so the intended application-level bounded-drain scenario is not pre-empted by the host's default UDP receive-buffer limit.

The present evidence does **not** establish exclusive ROS 2 actuator authority, protection against a hostile local process (including forged `/odom` or forged reset input), a measured or bounded reaction time, timing behaviour under representative load, a physical stopping-distance guarantee, hard real-time response, actual Nav2 controller-server interoperability, physical base-controller integration, measured wheel response, hardware STO behavior, validated human-distress perception, a formal safety proof, or conformity with a functional-safety standard. Standstill-qualified recovery is disabled by default in `GateParams`, `QerraGateNode` and the launch file; the stopping envelope is still computed from commanded velocity rather than measured velocity; and `/odom` verifies physical standstill only when backed by closed-loop wheel encoders or state estimation (`open_loop=false` in `diff_drive_controller`), not under `open_loop=true` or locked-wheel skidding. The `/odom` freshness watchdog uses callback receipt time rather than `Odometry.header.stamp` or encoder capture time, and its negative-age branch has no dedicated subtest. Phase 1 non-finite Twist handling now causes immediate **software command inhibition on the Gate evaluation tick**, without refreshing the proposer watchdog; it does not establish an instantaneous physical stop. Rapid alternating valid/invalid commands can refresh the held proposal timestamp on valid frames and alternate the output between commanded speed and zero without a separate chattering threshold. The `Twist` message still has no source timestamp, so callback receipt time is used.

The next engineering step is not to enlarge the claim. It is to close the measurable gaps: examine and define policy for rapid invalid/valid command chattering, improve the proposal timestamp and provenance contract (and use the odometry header or encoder capture stamp for the measurement watchdog), add a dedicated test for the `/odom` clock-regression branch, validate `w_standstill_tol_urad_s` and the fidelity of `/odom` standstill on real feedback, measure the reaction chain and relate the scan-freshness limit to it, enforce the ROS authority boundary and decide which local threats are in scope, validate complete scan geometry, measure deceleration, and formally analyze recovery invariants.

## References and Implementation Records

1. QERRA Supervisory Gate implementation: [`gate/gate_core.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/gate/gate_core.py), [`gate/gate_config.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/gate/gate_config.py), [`gate/gate_lidar.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/gate/gate_lidar.py), [`gate/hsr_telemetry.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/gate/hsr_telemetry.py) and [`gate/gate_log.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/gate/gate_log.py).
2. ROS 2 Jazzy node and HSR receiver: [`ros2/qerra_gate_node.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/ros2/qerra_gate_node.py), [`gate/hsr_receiver.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/gate/hsr_receiver.py) and [`ros2/hsr_receiver.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/ros2/hsr_receiver.py) (compatibility shim).
3. Package-discovery isolation boundary: [`src/qerra_msgs/COLCON_IGNORE`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/src/qerra_msgs/COLCON_IGNORE) masks the retained `src/qerra_msgs` source from `colcon` discovery. The standalone package manifest is [`package.xml`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/package.xml); the Jazzy build selects only `qerra_core` in [`.github/workflows/ros2_jazzy.yml`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/.github/workflows/ros2_jazzy.yml).
4. Safety concept and evidence anchors: [`SAFETY_CONCEPT.md`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/SAFETY_CONCEPT.md).
5. ROS 2 Jazzy CI workflow: [`.github/workflows/ros2_jazzy.yml`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/.github/workflows/ros2_jazzy.yml).
6. Python and HSR CI workflow: [`.github/workflows/tests.yml`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/.github/workflows/tests.yml).
7. Offline log verifier: [`verify_log.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/verify_log.py).
8. ROS 2 launch entry point: [`launch/qerra_gate.launch.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/launch/qerra_gate.launch.py).
9. Gate Core and flight-log regression tests: [`tests/test_gate_core.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/tests/test_gate_core.py) and [`tests/test_gate_log.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/tests/test_gate_log.py).
10. Host and ROS 2 node regression tests: [`tests/test_gate_ros2_node.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/tests/test_gate_ros2_node.py), [`tests/test_gate_ros2_node_wiring.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/tests/test_gate_ros2_node_wiring.py), and [`tests/test_gate_ros2_dual_protocol.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/tests/test_gate_ros2_dual_protocol.py).
11. Live topic traffic, remapping and Nav2-compatible exterior tests: [`tests/test_gate_ros2_live_traffic.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/tests/test_gate_ros2_live_traffic.py), [`tests/test_gate_ros2_remapping.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/tests/test_gate_ros2_remapping.py), and [`tests/test_gate_ros2_nav2_exterior.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/tests/test_gate_ros2_nav2_exterior.py).
12. Adversarial exploit and UDP flood tests: [`tests/test_adversarial_hsr.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/tests/test_adversarial_hsr.py).
13. Repository limitations: [`LIMITATIONS.md`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/LIMITATIONS.md).
14. Package metadata and changelog: [`package.xml`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/package.xml), [`setup.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/setup.py), and [`CHANGELOG.rst`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/CHANGELOG.rst).
15. ROS 2 Jazzy release process (Bloom): [First-time release guide](https://docs.ros.org/en/jazzy/How-To-Guides/Releasing/First-Time-Release.html) and [subsequent-release guide](https://docs.ros.org/en/jazzy/How-To-Guides/Releasing/Subsequent-Releases.html).

16. Layer 1B wire-contract conformance and HSR receiver diagnostics tests: [`tests/test_hsr_conformance.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/tests/test_hsr_conformance.py) and [`tests/test_hsr_receiver_diagnostics.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/tests/test_hsr_receiver_diagnostics.py).
17. `/odom` ingestion and freshness-watchdog tests (isolated ROS 2 stubs): [`tests/test_gate_ros2_odom.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/tests/test_gate_ros2_odom.py).
18. Webots supervisory controller with measured wheel-speed feedback: [`controllers/tiago_supervisory_gate/tiago_supervisory_gate.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/controllers/tiago_supervisory_gate/tiago_supervisory_gate.py).

**Standards named as informative design references only:** ISO 13849-1, ISO 13482, ISO 3691-4, and EN 50159.
