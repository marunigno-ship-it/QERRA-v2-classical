<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright (c) 2026 Marussa Metocharaki -->

# QERRA-v2 Classical: ROS 2 Jazzy Supervisory Gate and Assistive Reflex

## Technical Brief: Deterministic Kinematic Supervision, Reflex Telemetry, and Node-Level Fault Handling

**Author:** Marussa Metocharaki, Independent Researcher and Developer  
**Target audience:** Autonomous Mobile Robot (AMR) Systems Engineers, Functional Safety Researchers, and Verification Specialists  
**Date:** 8 November 2026  
**Document version:** 1.2.0  
**Software baseline:** Release v2.4.0 on `main`; `qerra_core` (`ament_python`); ROS 2 node `qerra_gate_node` v0.3.1; pure-function Gate Core v0.4; HSR telemetry contract `gate/hsr_telemetry.py` v0.3.1; `qerra_msgs` v2.2.1; flight-log schema v1 (`gate/gate_log.py`)  
**Safety concept baseline:** `SAFETY_CONCEPT.md` v0.10. Where this brief and the safety concept differ, this brief describes Release v2.4.0.  
**ROS distribution:** ROS 2 Jazzy Jalisco on Ubuntu 24.04 Noble  
**Simulation baseline:** Webots R2025a, PAL Robotics TIAGo model  
**Repository:** <https://github.com/marunigno-ship-it/QERRA-v2-classical>  
**Archive DOI:** <https://doi.org/10.5281/zenodo.24053163>

---

## Executive Summary

QERRA-v2 Classical contains a deterministic supervisory gate and an assistive reflex input path intended to constrain velocity commands before they reach a mobile robot base controller. This brief covers only Layer 1A, the kinematic Supervisory Gate, and Layer 1B, the QERRA-HSR reflex companion. SEMEV-12 and QERRA-THRIVE are outside the physical safety function described here.

The implementation consists of three distinct elements:

1. **Gate Core v0.4:** a pure-Python decision kernel implemented in `gate/gate_core.py`. Its transition function is `step(state, params, inputs) -> StepResult`. It has no ROS 2 dependency, file access, socket access, or direct clock access. Time is supplied as an explicit integer input in microseconds.
2. **ROS 2 Jazzy adapter:** `ros2/qerra_gate_node.py`, packaged as `qerra_core` using `ament_python`. The node receives proposed velocity commands and laser scans, polls HSR telemetry over non-blocking UDP, evaluates the gate, and publishes a constrained `Twist` command and diagnostic state. It can optionally write a hash-chained flight log.
3. **QERRA-HSR reflex path:** a three-vector status source evaluating `immediate_physical_distress`, `human_isolation`, and `environmental_hazard_proximity`. The ROS 2 gate receives its `CLEAR`, `MONITOR`, or `CRITICAL` status over UDP port 5008. A pure-function stream monitor checks the packet sequence before the status reaches the core.

The gate uses a dynamic stopping envelope based on commanded wheel speed, a configured deceleration, a reaction-time allowance, and a fixed margin. It also checks lidar scan integrity and freshness, proposer freshness, clock progression, and HSR status. A detected trip holds the software wheel command at zero. Recovery requires a continuous clear interval, a valid operator reset, and a quiescent reset tick before motion can resume.

The ROS 2 node has a nominal 32 ms control period (31.25 Hz). Its reaction-time and lidar-freshness parameters are exposed as two profiles, one for simulation and one for a 10 Hz scanner, and none of the values in either profile has been measured. The CI workflow builds and starts the package under ROS 2 Jazzy, builds the `qerra_msgs` interface package and instantiates its generated message types, checks that `/gate/state` publishes, checks for tick exceptions, and verifies clean SIGINT termination. Separate tests exercise the gate translators, the HSR receiver and stream monitor, the fault latch, node wiring, forged-input and fault-injection scenarios, and two executable exploit scenarios. In the Jazzy container, further tests drive the running node through live DDS topic traffic, and through live DDS traffic combined with UDP reflex telemetry, for a defined set of scenarios (section 5.6).

At Release v2.4.0 the author reports 217 host unit tests (211 passed, 6 cleanly skipped without `rclpy`) and 31 container integration tests, including live DDS topic traffic and dual-protocol reflex co-execution (section 5.2).

**Scope and safety status:** QERRA is an open-source simulation research prototype. The gate has been exercised in Webots R2025a, and the ROS 2 package has been built, started and exercised under live topic and UDP traffic in GitHub Actions Linux containers. The ROS 2 node has not been tested on a physical robot. No functional-safety certification, Performance Level, Safety Integrity Level, or standards conformity is claimed. A `0.0 m/s` output is a software velocity setpoint; it is not an emergency stop, a mechanical brake command, or a hardware Safe Torque Off (STO) function. References to ISO 13849-1, ISO 13482, ISO 3691-4 and EN 50159 are informative design references only. Localhost is treated as an assumed trusted process boundary (section 1.5); the gate does not defend against a hostile local process.

---

## 1. Architecture and Simplex Pattern

### 1.1 Functional partition

The architectural objective is to separate command generation from the final software decision to pass or clamp a velocity command. A planner, teleoperation source, or learned policy is treated as an untrusted proposer. The gate evaluates its proposal against independent sensor and reflex inputs before publishing the output setpoint.

```text
                 UNVERIFIED COMMAND PROPOSER
             (Nav2, teleoperation, learned policy)
                              |
                              | /cmd_vel
                              v
       +------------------------------------------------+
       |              QERRA ROS 2 GATE NODE             |
       |                qerra_gate_node                 |
       |                                                |
       |  /scan -----------------> Lidar pipeline       |
       |  UDP :5008 -------------> HSR receiver         |
       |                           + stream monitor     |
       |  /gate/reset -----------> Reset request        |
       |                                                |
       |  +------------------------------------------+  |
       |  | Gate Core v0.4                           |  |
       |  | step(state, params, inputs)               |  |
       |  |                                          |  |
       |  | Kinematic envelope / freshness / FSM     |  |
       |  +------------------------------------------+  |
       |                                                |
       |  NodeFaultLatch        optional flight log     |
       +----------------------+-------------------------+
                              |
                              | /cmd_vel_safe
                              v
                 BASE CONTROLLER INTERFACE
                              |
                              v
                     MOTOR DRIVES / WHEELS

            /gate/state <---- diagnostic publication
```

### 1.2 Separation of the ROS shell and the decision kernel

`gate/gate_core.py` is deliberately separated from ROS 2. The core receives explicit state, immutable parameters, and an input record. It returns a new state, wheel commands, a primary reason code, secondary events, and a record suitable for logging.

The core uses integer units for its decision and log quantities:

| Quantity | Representation |
|---|---|
| Time | microseconds (`us`) |
| Wheel angular speed | microradians per second (`urad/s`) |
| Distance | millimetres (`mm`) |
| Linear speed used by the envelope | millimetres per second (`mm/s`) |

This separation supports deterministic unit testing and replay of the core without requiring a ROS 2 installation. It does not, by itself, establish a hard real-time execution guarantee for the ROS 2 process that calls it. The HSR stream monitor (`step_hsr_stream`) follows the same pattern: a pure function of its state, the drained packets and the current time.

### 1.3 Relationship to Simplex Architecture

QERRA uses a **Simplex-inspired supervisory pattern**: an unverified command source proposes an action, while a lower-complexity deterministic gate evaluates whether the command may be passed to the actuator interface. The pattern follows the runtime-assurance idea behind the Simplex architecture.

The term *Simplex-inspired* is intentional. This implementation is not presented as a formally verified or complete implementation of the original Simplex architecture. The current gate is a command supervisor based on a stopping-distance test, freshness checks, and latched recovery. It does not provide a separately verified backup motion controller, a formal proof of an invariant safe set, or a proof that every possible robot state can be driven into a safe region.

### 1.4 Actuator authority boundary

The ROS 2 node subscribes to `/cmd_vel` and publishes `/cmd_vel_safe`. It is intended to be placed downstream of command multiplexing and upstream of the base controller. The base controller must be configured to accept commands only from the gate output path. Any direct planner, teleoperation, or alternate publisher path to the base controller would bypass the supervisor.

ROS 2 topic naming and ordinary publish/subscribe operation do not, by themselves, enforce exclusive write authority. The present node uses absolute topic names and does not configure SROS2 permissions or cryptographic publisher authentication. Therefore:

- Exclusive actuator authority is demonstrated in the Webots supervisory-controller topology, where the gate is the only process writing the simulated wheel velocities.
- In the standalone ROS 2 implementation, the gate publishes the designated safe output topic, but exclusive authority is a deployment requirement, not an access-control property established by the node.
- A physical integration would need an enforced command topology, controlled remapping, namespace isolation, DDS security policies, and protection against alternate command publishers.

The ROS 2 adapter should not be described as having proven exclusive physical actuator authority until this deployment boundary is enforced and tested.

### 1.5 Trust boundary

The project assumes that every process able to send to the gate's localhost UDP ports (5005, 5006, 5008) or to publish on its ROS topics is trusted. This is an assumption, not an achievement. The channels carry no authentication, no integrity code and no sender identity, and the node configures no SROS2 policy.

Protection against a hostile or compromised local process belongs outside the gate node: operating-system file permissions and user separation, exclusive socket binding, and SROS2 or equivalent access control on the ROS graph. In particular, a hostile process that can publish to `/cmd_vel_safe` bypasses the gate entirely, and no UDP authentication added to the gate would change that.

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
| `dt_us` | 32,000 us | Nominal control period |
| `t_watch_us` | 150,000 us | Proposer freshness limit |
| `t_stale_us` | 96,000 us (Webots and the ROS 2 simulation profile); 300,000 us (ROS 2 hardware profile) | Lidar freshness limit; node parameter `lidar_stale_ms` |
| `t_hsr_stale_us` | 96,000 us | HSR telemetry freshness limit |
| `t_dwell_us` | 1,000,000 us | Continuous-clear dwell before reset can be accepted |
| `max_tick_gap_us` | 64,000 us | Maximum inter-tick gap accepted during a continuous dwell |

The Webots controller passes a 32,000 us reaction allowance explicitly. The ROS 2 node passes the value of its `t_react_ms` parameter, converted to microseconds, to `get_live_gate_params()`. The generic `GateParams` data class retains a zero reaction-time default for backward compatibility.

The reference speed is derived from the larger positive wheel speed among the previous commanded wheel output and the newly clamped proposal. The core converts this wheel angular speed to a linear wheel speed using the configured wheel radius. Reverse commands are clamped because the current sensor arrangement does not provide a rearward stopping corridor.

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

The initial `GateState` is fail-closed and starts in `TRIPPED`. The node-level diagnostic value `FAULT` is produced by `NodeFaultLatch`; it is not a fourth mode in the Gate Core enum.

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

The core uses an explicit timestamp input. This makes its transition function reproducible for the same state, parameters, and input tuple. It does not make the ROS executor or operating-system scheduling deterministic.

### 3.3 HSR integration

The QERRA-HSR companion evaluates three normalized context vectors:

1. `immediate_physical_distress`
2. `human_isolation`
3. `environmental_hazard_proximity`

The ROS 2 node receives HSR status telemetry through a non-blocking UDP receiver on port 5008, bound to the local host. The receiver drains queued datagrams, passes the raw arrival-ordered batch through the stream monitor (section 3.5), and then applies worst-severity reduction (`CRITICAL` over `MONITOR` over `CLEAR`) to the batch. When HSR is required, a valid and fresh HSR status is part of the gate's input contract. `CRITICAL` causes a gate trip. Missing, stale, future-dated, or invalid required telemetry also causes a fail-closed trip.

HSR does not replace lidar obstacle geometry. The lidar path evaluates physical range in the forward corridor; HSR evaluates the supplied human-distress and contextual reflex status. The simulation demonstrations use synthetic or injected HSR inputs. They do not demonstrate validated perception of distress in a physical environment.

The ROS 2 node defaults to `hsr_source="udp"` and `hsr_required=true`. Explicit obstacle-only operation requires `hsr_source="none"` with `hsr_required=false`; the node rejects the contradictory configuration in which HSR is required but its source is disabled. The stream monitor's trips act through the gate's required-HSR path, so with `hsr_required=false` they do not stop the robot.

### 3.4 Recovery contract

A trip does not clear automatically when the immediate hazard disappears. Recovery is latched and requires:

1. The active trip conditions to clear.
2. An unbroken gate-level calm dwell of 1,000,000 us.
3. Continuous valid HSR `CLEAR` status for the required HSR clear-dwell interval when HSR is enabled.
4. Tick continuity: a gap greater than 64,000 us invalidates continuity for the gate dwell.
5. An explicit reset request whose source string is `operator`.
6. No active obstacle or HSR hazard at the time reset is evaluated.

A reset from any other source is rejected with `RESET_REJECTED_CHANNEL`. A reset while the gate is not ready is rejected with `RESET_REJECTED_NOT_READY`. A reset while an obstacle or non-clear HSR condition persists is rejected with `RESET_REJECTED_HAZARD`. The node-level ROS callback accepts the case-insensitive, whitespace-trimmed string `operator` on `/gate/reset`; this is a command convention, not proof of the sender's identity.

On the exact tick when reset is accepted, the core remains quiescent and returns zero wheel commands with reason `RESET_ACCEPTED`. The held proposal is not applied on that tick. Motion can resume on the subsequent nominal `RUN` cycle if the current inputs remain valid and no trip condition is present.

The HSR implementation also has its own stabilization logic. Where that upstream stabilization and the gate's independent clear dwell are both active, recovery is intentionally staged rather than immediate.

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

The ROS 2 package is `qerra_core`, built with `ament_python`. The node entry point is `ros2/qerra_gate_node.py`, with `NODE_VERSION = "0.3.1"`. It wraps Gate Core v0.4 and uses the following interfaces:

| Interface | Type | Role |
|---|---|---|
| `/cmd_vel` | `geometry_msgs/msg/Twist` | Proposed body velocity |
| `/scan` | `sensor_msgs/msg/LaserScan` | Lidar range input. The subscription uses `qos_profile_sensor_data` (Best Effort, Volatile) so that it matches physical lidar drivers. |
| `/gate/reset` | `std_msgs/msg/String` | Operator reset request |
| `/cmd_vel_safe` | `geometry_msgs/msg/Twist` | Gate output setpoint |
| `/gate/state` | `std_msgs/msg/String` | JSON diagnostic state |
| UDP port 5008 | QERRA-HSR telemetry | Reflex state input |
| UDP port 5007 | Gate clock/state message | Simulation producer clock interface |

Because the `/scan` subscription is Best Effort, scan messages can be dropped in transit. A dropped scan is not interpolated; the scan-freshness limit (section 3.2) is what turns a sustained loss into `TRIP_SENSOR_INVALID`.

`/gate/state` carries the node and gate versions, the mode (`RUN`, `TRIPPED`, `AWAITING_RESET`, or `FAULT`), the reason, the list of secondary `events` (for example `RESET_REJECTED_HAZARD`, which exposes rejected reset requests), `d_stop_mm`, `lidar_min_mm`, the HSR status and configuration (`hsr_source`, `hsr_required`, `hsr_drained_total`, `hsr_socket_error`), `fault_latched` and `fault_reason`, proposal sequence and age, the wheel commands in urad/s, and the active timing parameters `t_react_us`, `lidar_stale_us` and `lidar_period_us`.

The node parameters are:

| Parameter | Default | Meaning |
|---|---|---|
| `rate_hz` | 31.25 | Nominal tick rate (32 ms period) |
| `hsr_source` | `udp` | `udp`, or `none` for explicit obstacle-only mode |
| `hsr_required` | true | Trip if HSR telemetry is missing or stale |
| `hsr_port` | 5008 | UDP port for HSR datagrams |
| `state_port` | 5007 | UDP port for the clock echo |
| `lidar_n_expected` | 682 | Required beam count per scan |
| `lidar_fov_rad` | 4.1887902 | Scan field of view (240 degrees) |
| `robot_half_width_m` | 0.32 | Corridor half-width |
| `track_width_m`, `wheel_radius_m` | 0.4044, 0.098 | TIAGo base kinematics |
| `t_react_ms` | 96.0 | Reaction-time allowance (finite and non-negative) |
| `lidar_period_ms` | 32.0 | Assumed scan period |
| `lidar_stale_ms` | 96.0 | Scan freshness limit |
| `flight_log_path` | empty (disabled) | Path of the hash-chained flight log |

The default node timer period is 1/31.25 s, or 32 ms. This is a configured nominal period, not a measured worst-case dispatch interval.

### 4.2 Timing profiles and startup invariant

Three timing parameters (`t_react_ms`, `lidar_period_ms`, `lidar_stale_ms`) replace the single 32 ms Webots assumption. The node enforces at startup, and fails closed (refuses to start) if it is violated, the invariant

```text
lidar_stale_ms >= 2 * lidar_period_ms + dt_ms
```

The two documented profiles are:

| Profile | `lidar_period_ms` | `lidar_stale_ms` | `t_react_ms` | `d_stop` at 196 mm/s |
|---|---:|---:|---:|---:|
| Simulation (default) | 32.0 | 96.0 | 96.0 | 358 mm |
| Physical hardware, 10 Hz Hokuyo URG-04LX | 100.0 | 300.0 | 160.0 | 371 mm |

Both satisfy the invariant: 96 >= 2 x 32 + 32, and 300 >= 2 x 100 + 32.

The reaction-time values come from an engineering estimate of the signal chain, not from measurement:

| Component | Simulation | 10 Hz hardware | Basis |
|---|---|---|---|
| Scan period | 32 ms | 100 ms | Sensor update period |
| Transport | 2 to 4 ms | 2 to 4 ms | Estimate |
| Gate evaluation | 32 ms | 32 ms | One control period |
| Scheduling jitter | 10 to 15 ms | 10 to 15 ms | Estimate |
| Actuator response | 10 to 15 ms | 10 to 15 ms | Estimate |
| **Total** | **86 to 98 ms** | **154 to 166 ms** | |

The profile values (96 ms and 160 ms) lie inside these ranges. They are mid-range values, not upper bounds. Section 6.2 describes what this does and does not establish.

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
- `destroy_node()` flushes and closes the log file.
- `verify_log.py --replay` has reproduced the recorded decisions bit-for-bit in offline tests.

Log timestamps are ROS-clock microseconds. The log records gate commands, not wheel ground truth. A hash chain is tamper-evident only against a head hash stored somewhere else, and the node does not anchor its logs.

### 4.6 Interface package `qerra_msgs`

`src/qerra_msgs` (v2.2.1) defines the action `QerraEvaluate.action` for the SEMEV-12 moral-deliberation bridge, using primitive fields for goal, result and feedback. The CI workflow builds it together with `qerra_core` using:

```text
colcon build --paths src/qerra_core src/qerra_core/src/qerra_msgs --packages-select qerra_msgs qerra_core
```

The `--paths` option is needed because `qerra_msgs` is nested inside the repository root, which is itself the `qerra_core` package. A separate CI step, `Verify qerra_msgs action interface generation`, compiles the IDL and instantiates the generated Goal, Result and Feedback types in Python under ROS 2 Jazzy. This validates interface generation. The action server in `ros2_bridge.py` is not run in CI. The bridge is advisory and is not part of the safety function described in this brief.

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

The `SAFETY_CONCEPT.md` baseline records that the Demo 9 log replays bit-for-bit through Gate Core v0.4 using `verify_log.py --replay` (438 cycles). The archived Demo 9 run itself was produced with Gate v0.3; replay compatibility with v0.4 is not a new v0.4 live simulation run. The stream monitor, the timing profiles and the node flight log (sections 3.5, 4.2 and 4.5) were not part of either Webots run.

### 5.2 Unit-test baseline

The counts below are the author's reported results for Release v2.4.0, from a local Windows 11 run (Python 3.12 and 3.14) and the Jazzy container on 8 November 2026. The workflow logs are the authoritative record.

| Test group | Count | Evidence scope |
|---|---:|---|
| Host unit tests under `tests/` | 217 tests: 211 passed, 6 cleanly skipped without `rclpy`, 0 failures | Local Windows 11 run, 8 November 2026 |
| ROS 2 integration tests in the Jazzy container | 31 passing | 17 in `tests/test_gate_ros2_node.py`, 8 in `tests/test_gate_ros2_node_wiring.py`, 4 in `tests/test_gate_ros2_live_traffic.py`, 2 in `tests/test_gate_ros2_dual_protocol.py` |
| QERRA-HSR suite under `hsr/` | 20 passing | Last counted 1 November 2026; not part of the 217 |

The 6 skipped host tests are the 4 live topic traffic tests and the 2 dual-protocol tests, which need `rclpy`. The six fault-latch tests are in a separate file, `tests/test_gate_ros2_node_latch.py` (6 tests, last counted 1 November 2026). They are part of the host suite and are not among the 31 container tests. The host count also includes the stream-monitor edge-case matrix tests (6) and the adversarial exploit tests (2, section 5.5). Counts from overlapping local and CI test groups must not be added together as if they were independent tests. Test counts change as tests are added and should be updated from the test-run output.

### 5.3 Continuous integration

Both workflows pass at Release v2.4.0. Their run identifiers are in the GitHub Actions history. The earlier baseline at commit `a511d1e` was:

| Workflow | Run | Result |
|---|---|---|
| `QERRA-v2 Classical Test Suite` (`ubuntu-latest`, Python 3.10) | #766 | Passed in 1 min 11 s |
| `ROS 2 Jazzy Validation` (`ros:jazzy` container, Ubuntu 24.04) | #31 | Passed in 1 min 0 s |

The test-suite workflow runs the supervisory-gate suite (standard library only), the QERRA-HSR suite, a license and version boundary guard, and the SEMEV-12 regression.

The workflow `.github/workflows/ros2_jazzy.yml` runs in the official `ros:jazzy` container. Its checks include:

- Install dependencies and build `qerra_core` and `qerra_msgs` with `colcon` (section 4.6).
- Confirm that `qerra_gate_node` is discoverable as a package executable.
- Compile the `QerraEvaluate` action IDL and instantiate the generated Goal, Result and Feedback types.
- Start the installed executable from a neutral working directory.
- Capture one `/gate/state` message using `ros2 topic echo --once`.
- Confirm that the node log contains no `Tick exception` entry during the startup observation.
- Send SIGINT and assert process exit code 0.
- Instantiate the node under `rclpy` and check the expected HSR and lidar parameters.
- Run the ROS 2 node unit and wiring test files inside the Jazzy container.
- Run the live pub/sub topic traffic tests (`tests/test_gate_ros2_live_traffic.py`, 4 tests) and the live dual-protocol tests (`tests/test_gate_ros2_dual_protocol.py`, 2 tests) against the running node (section 5.6).

The workflow now exercises the node under live `/cmd_vel`, `/scan` and `/gate/reset` traffic over real DDS topics in the container, and under concurrent UDP Layer 1B reflex traffic. It does so for the specific scenarios listed in section 5.6: Best Effort lidar streaming, the 1.0 s clear dwell and operator reset, cruise passthrough, obstacle clamping, loss of the scan stream, loss of the proposal stream, refusal of a reset during a hazard, an acute distress packet during live cruise, and loss of the UDP heartbeat. Those scenarios are evidence for the behaviours stated and not a general proof of correctness.

The workflow does **not** measure end-to-end latency or timing under representative load; does not test a physical motor controller; does not run the `qerra_msgs` action server; and does not exercise the node flight log under ROS. The tests run on a shared CI runner in real time, so a pass is not a timing guarantee. The workflow is evidence of package construction, node initialization, publication, interface generation, the listed live scenarios, selected tests, and clean shutdown, not evidence of hardware functional safety.

### 5.4 Hash-chain verification

The flight recorder uses a rolling SHA-256 chain of canonicalized records:

$$
h_i = \operatorname{SHA256}(h_{i-1} \Vert \operatorname{canonical\_bytes}_i).
$$

The anchored Demo 7 and Demo 9 records can be checked offline with `verify_log.py`. A hash chain provides tamper-evidence relative to a trusted anchor; it does not prove that the recorded sensors, timestamps, or physical events were truthful or correctly measured. The node's optional log (section 4.5) uses the same format and has been checked offline with `verify_log.py --replay`, with no external anchor.

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

These are demonstrations of residual risk, not evidence of protection (section 6.6).

### 5.6 Live topic traffic and dual-protocol tests

These tests run in the `ros:jazzy` container and skip cleanly on hosts without `rclpy`. A harness drives the node through real DDS topics (`/cmd_vel`, `/scan` with Best Effort sensor-data QoS, `/gate/reset`) and observes `/cmd_vel_safe` and `/gate/state`.

**`tests/test_gate_ros2_live_traffic.py` (4 tests), HSR disabled so that Layer 1A is isolated:**

1. A clear corridor produces the 1.0 s dwell and `AWAITING_RESET`; an operator reset enters `RUN`; `/cmd_vel_safe` passes the proposal through; an obstacle breach trips `TRIP_OBSTACLE` and clamps `/cmd_vel_safe` to zero.
2. Silencing `/scan` produces `TRIP_SENSOR_INVALID` once the scan-freshness limit is exceeded.
3. An operator reset while an obstacle is present is refused (`RESET_REJECTED_HAZARD`, reported in the `events` list).
4. Silencing `/cmd_vel` produces `TRIP_PROPOSER_STALE` once the 150 ms proposal limit is exceeded.

**`tests/test_gate_ros2_dual_protocol.py` (2 tests), `hsr_required=true` and `hsr_source=udp` on port 5008 alongside live DDS traffic:**

1. The dual-dwell clear recovery completes; then a `CRITICAL` UDP packet injected during live DDS cruise trips `TRIP_HSR_CRITICAL` and clamps `/cmd_vel_safe` to zero.
2. Cutting the UDP stream while the DDS topics stay active trips `TRIP_HSR_STALE` and clamps `/cmd_vel_safe` to zero.

What these tests show: that, for these scenarios, the Layer 1A inputs (DDS) and the Layer 1B input (UDP) combine as designed in a real ROS 2 Jazzy environment, and that the scan subscription interoperates with a Best Effort publisher. What they do not show: timing bounds (the harness runs in real time on a shared runner), behaviour under representative CPU or I/O load, behaviour with a physical lidar driver, or any hostile-publisher scenario beyond section 5.5.

---

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

### 6.3 Commanded speed versus actual motion

The current core derives its stopping reference from commanded wheel velocities, not measured wheel encoder velocity or an independent state estimate. If the robot is still moving because of inertia, slip, slope, or a delayed controller response while the commanded velocity has already fallen, the calculated stopping envelope may be smaller than the distance required to stop the physical platform.

A measured-motion input and a validated deceleration model are necessary before the envelope can support physical safety claims.

### 6.4 Geometric and sensor coverage limits

The corridor filter approximates a straight forward swept corridor. It does not model the robot's full rotating footprint, the swept path of a pivot or curved turn, or rearward motion. The current reverse clamp is a consequence of the absence of a rear sensor path, not proof that the robot is safe during every differential-drive maneuver.

The ROS 2 adapter checks scan length but does not verify all `LaserScan` angular metadata or the sensor-to-base transform. The raw minimum-return check can be satisfied by lateral returns even when the forward sector is occluded. These limits require sensor-specific validation and improved geometric coverage checks.

### 6.5 Proposer freshness and command provenance

The pure core can validate an explicit proposal timestamp. In the ROS 2 wrapper, however, the adapter assigns the current node time when a `Twist` callback receives a message. Since `geometry_msgs/msg/Twist` has no source timestamp or publisher identity, the 150 ms watchdog does not prove the age of the planner's original command. DDS queueing can also delay callback processing.

A deployment should use a stamped proposal interface, define a clock-domain policy, validate source identity and sequence progression, and test queue behavior under congestion and replay.

### 6.6 Authentication, trust boundary and forged-input sequences

The `/gate/reset` topic accepts the string `operator` but does not authenticate the publisher. The UDP HSR receiver and the operator-reset socket are bound to the local host, but they provide no sender authentication, integrity code or replay protection. The node does not configure SROS2 governance and permission policies. Absolute topic names also require deliberate namespace and remapping design for multi-robot deployments. Authentication, authorization, anti-replay measures, network isolation, and process privilege separation remain deployment requirements.

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

### 6.8 Timing and formal assurance boundary

The project has deterministic core logic and automated tests. The current evidence does not include a formal proof of the gate's safety invariants, model checking of all state transitions, worst-case execution-time analysis, or statistical reaction-time distributions. A 31.25 Hz timer configuration is not a WCET result.

### 6.9 Perception stream monitor limits

The stream monitor (section 3.5) detects counter faults. It does not detect a frozen sensor behind a live producer: a producer that republishes the same camera frame with a fresh counter and fresh timestamps passes every check. Stamps are supplied by the producer, and the synthetic producer stamps from the clock echo, not from sensor capture, so the freshness checks measure the producer loop, not the sensor. The monitor protects only when `hsr_required` is true.

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

**Required work:** Conduct instrumented, repeatable stops at controlled speeds and payloads. Compare commanded wheel speed with encoder-derived and independently measured platform velocity. Derive conservative deceleration bounds and quantify run-to-run variation. No stopping claim should be generalized beyond the tested configuration.

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

QERRA-v2 Classical provides an inspectable deterministic gate core, a ROS 2 Jazzy node wrapper, a forward lidar corridor filter, an HSR telemetry input with a sequence-checking stream monitor, a latched recovery contract, node-level fault handling, parameterised timing profiles, and an optional hash-chained flight log. The core's separation from ROS 2, explicit state inputs, integer decision units, and reproducible simulation logs provide a concrete basis for further systems-engineering evaluation.

The present evidence supports the following statements:

- The Gate Core v0.4 is implemented as a deterministic pure-function component and is covered by unit tests.
- The supervisory gate and HSR reflex behavior have been demonstrated in the specified Webots scenarios.
- The standalone `qerra_core` ROS 2 package builds and starts under ROS 2 Jazzy in GitHub Actions, and the `qerra_msgs` action interface generates and instantiates there.
- The CI baseline is 31 container integration tests. They include live DDS topic traffic (`/cmd_vel`, `/scan` with Best Effort QoS, `/gate/reset`) and concurrent UDP Layer 1B reflex traffic, covering the scenarios in section 5.6, in a real ROS 2 Jazzy environment.
- The node publishes diagnostic state, including secondary gate events, handles the tested SIGINT lifecycle, and includes a process-lifetime tick fault latch.
- The core refuses the specific forged and malformed inputs listed in section 5.5, and two executable exploit tests demonstrate what it does not prevent.

The present evidence does **not** establish exclusive ROS 2 actuator authority, protection against a hostile local process, a measured or bounded reaction time, timing behaviour under representative load, a physical stopping-distance guarantee, hard real-time response, hardware STO behavior, validated human-distress perception, a formal safety proof, or conformity with a functional-safety standard.

The next engineering step is not to enlarge the claim. It is to close the measurable gaps: measure the reaction chain and relate the scan-freshness limit to it, enforce the ROS authority boundary and decide which local threats are in scope, correct the proposal timestamp and provenance contract, validate complete scan geometry, measure deceleration, and formally analyze recovery invariants.

---

## References and Implementation Records

1. QERRA Supervisory Gate implementation: [`gate/gate_core.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/gate/gate_core.py), [`gate/gate_config.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/gate/gate_config.py), [`gate/gate_lidar.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/gate/gate_lidar.py), [`gate/hsr_telemetry.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/gate/hsr_telemetry.py) and [`gate/gate_log.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/gate/gate_log.py).
2. ROS 2 Jazzy node and HSR receiver: [`ros2/qerra_gate_node.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/ros2/qerra_gate_node.py) and [`ros2/hsr_receiver.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/ros2/hsr_receiver.py).
3. Interface package: [`src/qerra_msgs`](https://github.com/marunigno-ship-it/QERRA-v2-classical/tree/main/src/qerra_msgs).
4. Safety concept and evidence anchors: [`SAFETY_CONCEPT.md`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/SAFETY_CONCEPT.md).
5. ROS 2 Jazzy CI workflow: [`.github/workflows/ros2_jazzy.yml`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/.github/workflows/ros2_jazzy.yml).
6. Python and HSR CI workflow: [`.github/workflows/tests.yml`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/.github/workflows/tests.yml).
7. Offline log verifier: [`verify_log.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/verify_log.py).
8. Live traffic and dual-protocol tests: [`tests/test_gate_ros2_live_traffic.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/tests/test_gate_ros2_live_traffic.py) and [`tests/test_gate_ros2_dual_protocol.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/tests/test_gate_ros2_dual_protocol.py).
9. Adversarial exploit tests: [`tests/test_adversarial_hsr.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/tests/test_adversarial_hsr.py).
10. Repository limitations: [`LIMITATIONS.md`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/LIMITATIONS.md).

**Standards named as informative design references only:** ISO 13849-1, ISO 13482, ISO 3691-4, and EN 50159.
