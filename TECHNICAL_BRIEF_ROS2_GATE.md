<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright (c) 2026 Marussa Metocharaki -->

# QERRA-v2 Classical: ROS 2 Jazzy Supervisory Gate and Assistive Reflex

## Technical Brief: Deterministic Kinematic Supervision, Reflex Telemetry, and Node-Level Fault Handling

**Author:** Marussa Metocharaki, Independent Researcher and Developer  
**Location:** Greece  
**Target audience:** Autonomous Mobile Robot (AMR) Systems Engineers, Functional Safety Researchers, and Verification Specialists  
**Date:** 2 November 2026  
**Document version:** 1.0.0  
**Software baseline:** `qerra_core` (`ament_python`); ROS 2 node `qerra_gate_node` v0.3.0; pure-function Gate Core v0.4  
**Safety concept baseline:** `SAFETY_CONCEPT.md` v0.9, dated 1 November 2026  
**ROS distribution:** ROS 2 Jazzy Jalisco on Ubuntu 24.04 Noble  
**Simulation baseline:** Webots R2025a, PAL Robotics TIAGo model  
**Repository:** <https://github.com/marunigno-ship-it/QERRA-v2-classical>  
**Archive DOI:** <https://doi.org/10.5281/zenodo.23836773>

---

## Executive Summary

QERRA-v2 Classical contains a deterministic supervisory gate and an assistive reflex input path intended to constrain velocity commands before they reach a mobile robot base controller. This brief covers only Layer 1A, the kinematic Supervisory Gate, and Layer 1B, the QERRA-HSR reflex companion. SEMEV-12 and QERRA-THRIVE are outside the physical safety function described here.

The implementation consists of three distinct elements:

1. **Gate Core v0.4:** a pure-Python decision kernel implemented in `gate/gate_core.py`. Its transition function is `step(state, params, inputs) -> StepResult`. It has no ROS 2 dependency, file access, socket access, or direct clock access. Time is supplied as an explicit integer input in microseconds.
2. **ROS 2 Jazzy adapter:** `ros2/qerra_gate_node.py`, packaged as `qerra_core` using `ament_python`. The node receives proposed velocity commands and laser scans, polls HSR telemetry over non-blocking UDP, evaluates the gate, and publishes a constrained `Twist` command and diagnostic state.
3. **QERRA-HSR reflex path:** a three-vector status source evaluating `immediate_physical_distress`, `human_isolation`, and `environmental_hazard_proximity`. The ROS 2 gate receives its `CLEAR`, `MONITOR`, or `CRITICAL` status over UDP port 5008.

The gate uses a dynamic stopping envelope based on commanded wheel speed, a configured deceleration, a reaction-time allowance, and a fixed margin. It also checks lidar scan integrity and freshness, proposer freshness, clock progression, and HSR status. A detected trip holds the software wheel command at zero. Recovery requires a continuous clear interval, a valid operator reset, and a quiescent reset tick before motion can resume.

The ROS 2 node has a nominal 32 ms control period (31.25 Hz). Its CI workflow builds and starts the package under ROS 2 Jazzy, checks that `/gate/state` publishes, checks for tick exceptions, and verifies clean SIGINT termination. Separate tests exercise the gate translators, HSR receiver, fault latch, and node wiring.

**Scope and safety status:** QERRA is an open-source simulation research prototype. The gate has been exercised in Webots R2025a and the ROS 2 package has been built and started in GitHub Actions Linux containers. The ROS 2 node has not been tested on a physical robot. No functional-safety certification, Performance Level, Safety Integrity Level, or standards conformity is claimed. A `0.0 m/s` output is a software velocity setpoint; it is not an emergency stop, a mechanical brake command, or a hardware Safe Torque Off (STO) function. References to ISO 13849-1, ISO 13482, and ISO 3691-4 are informative design references only.

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
       |  /gate/reset -----------> Reset request        |
       |                                                |
       |  +------------------------------------------+  |
       |  | Gate Core v0.4                           |  |
       |  | step(state, params, inputs)               |  |
       |  |                                          |  |
       |  | Kinematic envelope / freshness / FSM     |  |
       |  +------------------------------------------+  |
       |                                                |
       |  NodeFaultLatch                                |
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

This separation supports deterministic unit testing and replay of the core without requiring a ROS 2 installation. It does not, by itself, establish a hard real-time execution guarantee for the ROS 2 process that calls it.

### 1.3 Relationship to Simplex Architecture

QERRA uses a **Simplex-inspired supervisory pattern**: an unverified command source proposes an action, while a lower-complexity deterministic gate evaluates whether the command may be passed to the actuator interface. The separation is consistent with the central runtime-assurance motivation of the Simplex architecture described by Seto, Krogh, Sha, and Chutinan (1998).

The term *Simplex-inspired* is intentional. This implementation is not presented as a formally verified or complete implementation of the original Simplex architecture. The current gate is a command supervisor based on a stopping-distance test, freshness checks, and latched recovery. It does not provide a separately verified backup motion controller, a formal proof of an invariant safe set, or a proof that every possible robot state can be driven into a safe region.

### 1.4 Actuator authority boundary

The ROS 2 node subscribes to `/cmd_vel` and publishes `/cmd_vel_safe`. It is intended to be placed downstream of command multiplexing and upstream of the base controller. The base controller must be configured to accept commands only from the gate output path. Any direct planner, teleoperation, or alternate publisher path to the base controller would bypass the supervisor.

ROS 2 topic naming and ordinary publish/subscribe operation do not, by themselves, enforce exclusive write authority. The present node uses absolute topic names and does not configure SROS2 permissions or cryptographic publisher authentication. Therefore:

- Exclusive actuator authority is demonstrated in the Webots supervisory-controller topology, where the gate is the only process writing the simulated wheel velocities.
- In the standalone ROS 2 implementation, the gate publishes the designated safe output topic, but exclusive authority is a deployment requirement, not an access-control property established by the node.
- A physical integration would need an enforced command topology, controlled remapping, namespace isolation, DDS security policies, and protection against alternate command publishers.

The ROS 2 adapter should not be described as having proven exclusive physical actuator authority until this deployment boundary is enforced and tested.

---

## 2. Kinematic Stopping Envelope and Corridor Filter

### 2.1 Stopping-distance calculation

The gate evaluates obstacle clearance against a stopping-distance envelope recalculated from a reference velocity on each control tick.

In integer millimetre units:

\[
 d_{\mathrm{stop,mm}}(v) =
 \left\lceil \frac{v_{\mathrm{mm/s}}^2}
 {2a_{\mathrm{design,mm/s^2}}} \right\rceil
 +
 \left\lceil \frac{v_{\mathrm{mm/s}}\,t_{\mathrm{react,us}}}
 {10^6} \right\rceil
 + m_{\mathrm{mm}}.
\]

The parameters used by the current live gate configuration are:

| Parameter | Value | Interpretation |
|---|---:|---|
| `a_design_mmps2` | 500 mm/s^2 | Design deceleration, equivalent to 0.5 m/s^2 |
| `t_react_us` | 32,000 us | One 32 ms simulation control step |
| `margin_mm` | 300 mm | Fixed standstill clearance margin |
| `dt_us` | 32,000 us | Nominal control period |
| `t_watch_us` | 150,000 us | Proposer freshness limit |
| `t_stale_us` | 96,000 us | Lidar freshness limit |
| `t_hsr_stale_us` | 96,000 us | HSR telemetry freshness limit |
| `t_dwell_us` | 1,000,000 us | Continuous-clear dwell before reset can be accepted |
| `max_tick_gap_us` | 64,000 us | Maximum inter-tick gap accepted during a continuous dwell |

The live configuration factory `gate/gate_config.py` supplies the 32,000 us reaction allowance. The generic `GateParams` data class retains a zero reaction-time default for backward compatibility; the standalone node uses the live configuration factory.

The reference speed is derived from the larger positive wheel speed among the previous commanded wheel output and the newly clamped proposal. The core converts this wheel angular speed to a linear wheel speed using the configured wheel radius. Reverse commands are clamped because the current sensor arrangement does not provide a rearward stopping corridor.

### 2.2 Nominal cruise calculation

For equal wheel speeds of 2.0 rad/s and a wheel radius of 0.098 m:

\[
 v = 2.0 \times 0.098 = 0.196\ \mathrm{m/s}
\]

With a design deceleration of 0.5 m/s^2 and a reaction allowance of 0.032 s:

\[
 d_{\mathrm{brake}} =
 \left\lceil \frac{0.196^2}{2\times0.5}\times1000 \right\rceil
 = 39\ \mathrm{mm}
\]

\[
 d_{\mathrm{react}} =
 \left\lceil 0.196\times0.032\times1000 \right\rceil
 = 7\ \mathrm{mm}
\]

\[
 d_{\mathrm{stop}} = 39 + 7 + 300 = 346\ \mathrm{mm}.
\]

This is the configured software envelope at the stated commanded speed. It is not a measured physical stopping-distance guarantee.

### 2.3 Lidar corridor filter

`gate/gate_lidar.py` provides a forward corridor filter. The current node defaults are:

- Expected scan length: 682 range samples.
- Configured field of view: 240 degrees.
- Corridor half-width: 0.32 m.
- Robot base half-width assumption: 0.27 m.
- Additional lateral allowance: 0.05 m.

The resulting nominal corridor width is 0.64 m. The filter treats the scan samples as evenly distributed over a symmetric field of view. For each valid range, it determines whether the corresponding projected point lies ahead of the sensor and within the configured lateral half-width. Valid points outside that corridor are replaced with positive infinity (`+inf`), leaving the array length unchanged. Invalid values are not converted into clear readings; they are passed to the core for rejection.

The core validates scan presence, sample count, timestamp age, values, and the minimum raw return count. A sample-count mismatch is discarded by the ROS 2 adapter and results in a fail-closed sensor-invalid condition. The current live configuration requires at least five finite raw returns across the scan.

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
| `TRIP_HSR_INVALID` | Required HSR status is missing, malformed, or not one of the defined states |
| `TRIP_CLOCK_ANOMALY` | The supplied gate timestamp is not strictly greater than the previous tick timestamp |
| `TRIP_LOG_FAILURE` | The caller reports a log-write failure to the core |

The proposer threshold is 150,000 us. Lidar and HSR freshness limits are 96,000 us. In the core implementation, HSR staleness is triggered when the age is greater than 96,000 us; a future-dated HSR observation is invalid.

The core uses an explicit timestamp input. This makes its transition function reproducible for the same state, parameters, and input tuple. It does not make the ROS executor or operating-system scheduling deterministic.

### 3.3 HSR integration

The QERRA-HSR companion evaluates three normalized context vectors:

1. `immediate_physical_distress`
2. `human_isolation`
3. `environmental_hazard_proximity`

The ROS 2 node receives HSR status telemetry through a non-blocking UDP receiver on port 5008. The receiver drains queued datagrams and applies worst-severity reduction (`CRITICAL` over `MONITOR` over `CLEAR`) before returning the latest batch result. When HSR is required, a valid and fresh HSR status is part of the gate's input contract. `CRITICAL` causes a gate trip. Missing, stale, future-dated, or invalid required telemetry also causes a fail-closed trip.

HSR does not replace lidar obstacle geometry. The lidar path evaluates physical range in the forward corridor; HSR evaluates the supplied human-distress and contextual reflex status. The simulation demonstrations use synthetic or injected HSR inputs. They do not demonstrate validated perception of distress in a physical environment.

The ROS 2 node defaults to `hsr_source="udp"` and `hsr_required=true`. Explicit obstacle-only operation requires `hsr_source="none"` with `hsr_required=false`; the node rejects the contradictory configuration in which HSR is required but its source is disabled.

### 3.4 Recovery contract

A trip does not clear automatically when the immediate hazard disappears. Recovery is latched and requires:

1. The active trip conditions to clear.
2. An unbroken gate-level calm dwell of 1,000,000 us.
3. Continuous valid HSR `CLEAR` status for the required HSR clear-dwell interval when HSR is enabled.
4. Tick continuity: a gap greater than 64,000 us invalidates continuity for the gate dwell.
5. An explicit reset request whose source string is `operator`.
6. No active obstacle or HSR hazard at the time reset is evaluated.

A reset while the gate is not ready is rejected. A reset while an obstacle or non-clear HSR condition persists is rejected with `RESET_REJECTED_HAZARD`. The node-level ROS callback accepts the case-insensitive, whitespace-trimmed string `operator` on `/gate/reset`; this is a command convention, not proof of the sender's identity.

On the exact tick when reset is accepted, the core remains quiescent and returns zero wheel commands with reason `RESET_ACCEPTED`. The held proposal is not applied on that tick. Motion can resume on the subsequent nominal `RUN` cycle if the current inputs remain valid and no trip condition is present.

The HSR implementation also has its own stabilization logic. Where that upstream stabilization and the gate's independent clear dwell are both active, recovery is intentionally staged rather than immediate.

---

## 4. ROS 2 Node Hardening and Fault Latching

### 4.1 Package and node boundary

The ROS 2 package is `qerra_core`, built with `ament_python`. The node entry point is `ros2/qerra_gate_node.py`, with `NODE_VERSION = "0.3.0"`. It wraps Gate Core v0.4 and uses the following interfaces:

| Interface | Type | Role |
|---|---|---|
| `/cmd_vel` | `geometry_msgs/msg/Twist` | Proposed body velocity |
| `/scan` | `sensor_msgs/msg/LaserScan` | Lidar range input |
| `/gate/reset` | `std_msgs/msg/String` | Operator reset request |
| `/cmd_vel_safe` | `geometry_msgs/msg/Twist` | Gate output setpoint |
| `/gate/state` | `std_msgs/msg/String` | JSON diagnostic state |
| UDP port 5008 | QERRA-HSR telemetry | Reflex state input |
| UDP port 5007 | Gate clock/state message | Simulation producer clock interface |

The default node timer period is 1/31.25 s, or 32 ms. This is a configured nominal period, not a measured worst-case dispatch interval.

### 4.2 NodeFaultLatch

`NodeFaultLatch` is a pure-Python latch in `ros2/qerra_gate_node.py`. It records the first fault reason and does not overwrite it with later faults. When an unhandled exception occurs inside `_tick_callback`, the node trips the latch, publishes a zero `Twist`, and publishes `/gate/state` diagnostics containing `mode="FAULT"` and a `NODE_FAULT_LATCHED` reason.

On subsequent timer callbacks, the latched path short-circuits the normal gate evaluation, continues publishing a zero `Twist`, and retains the original fault reason. The latch cannot be cleared by `/gate/reset`. It persists for the lifetime of the process and is cleared only when a new process instance is started.

The latch is an application-level response to exceptions in the control-tick path. It is not an independent hardware safety channel. It does not protect against process termination, kernel failure, loss of power, a blocked executor that cannot run the next tick, or failure of the publisher or downstream command path. The ROS 2 node also does not make every constructor and subscription callback part of one global exception boundary.

Automatic process supervision must not be allowed to restart a faulted node and restore motion without an independent inspection and re-arm policy. A process restart resets the in-memory latch.

### 4.3 Shutdown handling

The node entry point catches `KeyboardInterrupt` and `rclpy.executors.ExternalShutdownException`. In the `finally` path it destroys the node and calls `rclpy.shutdown()` only when `rclpy.ok()` is true. The Jazzy CI workflow asserts that SIGINT results in process exit code 0.

A clean SIGINT exit is a lifecycle property. It is not evidence that a physical base has entered a safe state. The shutdown path does not establish a certified stop function, and a process that stops publishing may leave a downstream controller holding its last command, depending on that controller's command timeout and behavior. A physical system needs a separately specified and tested downstream watchdog or safety-rated stop path.

### 4.4 Audit output boundary

The SHA-256 rolling hash-chain flight recorder is implemented in the Webots supervisory-controller evidence path. The standalone ROS 2 node currently publishes diagnostic JSON on `/gate/state`; it does not yet write the same hash-chained flight log. Webots log integrity evidence must not be attributed to the ROS 2 node.

---

## 5. Empirical Evidence Baseline

Evidence is reported by scope. A passing unit test, a Webots run, and a ROS 2 package-startup test are different forms of evidence and are not interchangeable.

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

The `SAFETY_CONCEPT.md` baseline records that the Demo 9 log replays bit-for-bit through Gate Core v0.4 using `verify_log.py --replay` (438 cycles). The archived Demo 9 run itself was produced with Gate v0.3; replay compatibility with v0.4 is not a new v0.4 live simulation run.

### 5.2 Unit-test baseline

The supplied November 2026 baseline reports:

| Test group | Count | Evidence scope |
|---|---:|---|
| Host tests discovered under `tests/test_*.py` | 192 passing | Local host unit-test discovery |
| QERRA-HSR suite under `hsr/` | 20 passing | Reflex and hysteresis unit tests |
| ROS 2 node unit/wiring tests | 20 passing | Translators, HSR integration/receiver, fault latch, and node wiring |
| Aggregate Linux CI baseline | 206+ passing | Project-reported aggregate across CI test workflows |

The 20 ROS 2 node tests are reported as 11 translator/HSR integration tests, 6 fault-latch tests, and 3 node-wiring tests. Test counts are tied to the stated November 2026 baseline and should be updated from the test-run output when the suite changes. Counts from overlapping local and CI test groups must not be added together as if they were independent tests.

### 5.3 ROS 2 Jazzy continuous integration

The workflow `.github/workflows/ros2_jazzy.yml` runs in the official `ros:jazzy` container on Ubuntu 24.04. Its checks include:

- Install dependencies and build `qerra_core` with `colcon`.
- Confirm that `qerra_gate_node` is discoverable as a package executable.
- Start the installed executable from a neutral working directory.
- Capture one `/gate/state` message using `ros2 topic echo --once`.
- Confirm that the node log contains no `Tick exception` entry during the startup observation.
- Send SIGINT and assert process exit code 0.
- Instantiate the node under `rclpy` and check the expected HSR and lidar parameters.
- Run the ROS 2 node unit and wiring test files inside the Jazzy container.

The supplied baseline records GitHub Actions run #7, commit `a7a00ba`, passing in 43 seconds with exit code 0 asserted.

The workflow does **not** establish correct behavior under live `/cmd_vel`, `/scan`, and `/gate/reset` traffic; does not measure end-to-end latency or timing under load; does not test a physical motor controller; and does not build the separate `qerra_msgs` interface package. The workflow is evidence of package construction, node initialization, basic publication, selected tests, and clean shutdown—not evidence of hardware functional safety.

### 5.4 Hash-chain verification

The Webots flight recorder uses a rolling SHA-256 chain of canonicalized records:

\[
 h_i = \operatorname{SHA256}(h_{i-1} \Vert \operatorname{canonical\_bytes}_i).
\]

The anchored Demo 7 and Demo 9 records can be checked offline with `verify_log.py`. A hash chain provides tamper-evidence relative to a trusted anchor; it does not prove that the recorded sensors, timestamps, or physical events were truthful or correctly measured. The current ROS 2 node does not yet emit this same hash-chained flight log.

---

## 6. Epistemic Limits and Safety Honesty Boundaries

The following limits define what can and cannot be concluded from the current evidence.

### 6.1 Simulation and hardware boundary

The gate has been evaluated in Webots R2025a, and the ROS 2 package has been built and started in Linux CI. No physical robot, physical laser scanner, motor driver, brake, or hardware emergency-stop interface has been tested as part of the stated baseline. There are no measured wheel-slip, payload, surface-friction, gradient, or battery-state distributions.

### 6.2 Reaction-time model

The 32 ms `t_react` allowance is derived from one Webots discrete control step. The ROS 2 node has a nominal 32 ms timer period, but general-purpose Ubuntu Linux and `rclpy` do not provide a hard real-time deadline guarantee.

A physical reaction-time budget must include, at minimum:

- Scanner acquisition and scan publication period. A 10 Hz scanner has a nominal 100 ms scan period; phase and device-specific timing must be measured.
- Sensor driver and operating-system scheduling delays.
- DDS transport, middleware queues, and executor dispatch.
- Gate evaluation and publication delays.
- Base-controller reception and update timing.
- Motor-driver ramp-down and the measured mechanical deceleration response.

The configured 32 ms allowance is therefore optimistic for a physical ROS deployment until the complete chain has been instrumented and the stopping envelope recalculated from measured latency and deceleration bounds.

### 6.3 Commanded speed versus actual motion

The current core derives its stopping reference from commanded wheel velocities, not measured wheel encoder velocity or an independent state estimate. If the robot is still moving because of inertia, slip, slope, or a delayed controller response while the commanded velocity has already fallen, the calculated stopping envelope may be smaller than the distance required to stop the physical platform.

A measured-motion input and a validated deceleration model are necessary before the envelope can support physical safety claims.

### 6.4 Geometric and sensor coverage limits

The corridor filter approximates a straight forward swept corridor. It does not model the robot's full rotating footprint, the swept path of a pivot or curved turn, or rearward motion. The current reverse clamp is a consequence of the absence of a rear sensor path, not proof that the robot is safe during every differential-drive maneuver.

The ROS 2 adapter checks scan length but does not verify all `LaserScan` angular metadata or the sensor-to-base transform. The raw minimum-return check can be satisfied by lateral returns even when the forward sector is occluded. These limits require sensor-specific validation and improved geometric coverage checks.

### 6.5 Proposer freshness and command provenance

The pure core can validate an explicit proposal timestamp. In the ROS 2 wrapper, however, the adapter assigns the current node time when a `Twist` callback receives a message. Since `geometry_msgs/msg/Twist` has no source timestamp or publisher identity, the 150 ms watchdog does not prove the age of the planner's original command. DDS queueing can also delay callback processing.

A deployment should use a stamped proposal interface, define a clock-domain policy, validate source identity and sequence progression, and test queue behavior under congestion and replay.

### 6.6 Authentication and ROS graph security

The `/gate/reset` topic accepts the string `operator` but does not authenticate the publisher. The UDP HSR receiver is non-blocking and bound to the local host by default, but it does not provide cryptographic sender authentication. A local process with access to the ROS graph or loopback UDP interface may be able to inject a reset or HSR packet.

The node does not configure SROS2 governance and permission policies. Absolute topic names also require deliberate namespace and remapping design for multi-robot deployments. Authentication, authorization, anti-replay measures, network isolation, and process privilege separation remain deployment requirements.

### 6.7 Process failure and software setpoint boundary

A zero `Twist` is a software command. It does not remove drive power, apply a certified mechanical brake, or invoke hardware STO. A Python process cannot guarantee that it will publish a zero command after abrupt termination, a kernel failure, a process crash outside the handled tick path, or a loss of communication.

A physical design would require an independent downstream command timeout or hardware watchdog and a safety-rated stop path appropriate to the target platform. The application-level node fault latch is not a substitute for those mechanisms.

### 6.8 Timing and formal assurance boundary

The project has deterministic core logic and automated tests. The current evidence does not include a formal proof of the gate's safety invariants, model checking of all state transitions, worst-case execution-time analysis, or statistical reaction-time distributions. A 31.25 Hz timer configuration is not a WCET result.

### 6.9 Standards boundary

ISO 13849-1, ISO 13482, and ISO 3691-4 are informative design references in this research prototype. No clause-by-clause conformity assessment, risk-reduction validation, Performance Level calculation, Safety Integrity Level calculation, certification, or approval is claimed.

---

## 7. Concrete Research Collaboration Vectors

The following are defined engineering work packages. Each requires evidence beyond the current simulation and CI baseline.

### Vector 1 — End-to-end reaction-time measurement

**Objective:** Replace the assumed 32 ms reaction allowance with measured timing data for a complete ROS 2 and actuator chain.

**Research question:** What are the observed minimum, median, p95, p99, maximum, and experimentally justified upper bounds from scanner acquisition to gate trip, safe-command publication, base-controller reception, and measured wheel deceleration?

**Required work:** Instrument acquisition timestamps, ROS callback dispatch, timer start and completion, publication, controller reception, and wheel feedback. Record clock synchronization error and load conditions. Report distributions by sensor rate, executor configuration, CPU load, DDS configuration, and network topology. Re-derive `t_react` and `d_stop` from the measured chain.

### Vector 2 — Hardware stopping-distance characterization

**Objective:** Establish whether the 0.5 m/s^2 design deceleration and 300 mm margin are appropriate for a defined platform envelope.

**Research question:** How do payload, floor material, gradient, wheel wear, battery state, caster behavior, and commanded turning rate affect physical stopping distance?

**Required work:** Conduct instrumented, repeatable stops at controlled speeds and payloads. Compare commanded wheel speed with encoder-derived and independently measured platform velocity. Derive conservative deceleration bounds and quantify run-to-run variation. No stopping claim should be generalized beyond the tested configuration.

### Vector 3 — ROS 2 actuator authority and security topology

**Objective:** Make the gate's authority boundary enforceable rather than conventional.

**Research question:** Which combination of command remapping, namespace isolation, DDS permissions, process privileges, and base-controller configuration prevents any untrusted publisher from bypassing the gate or issuing an unauthorized reset?

**Required work:** Define the complete ROS graph, demonstrate that the base controller accepts only the gate output, test unauthorized publisher attempts, validate reset authorization, and verify behavior after gate process death and communication loss. Include multi-robot namespace and domain-isolation tests.

### Vector 4 — Formal state-machine verification

**Objective:** Specify the Gate Core transition system and check recovery and fail-closed properties independently of implementation tests.

**Research question:** Under what assumptions can the system guarantee that a trip cannot transition to motion without continuous-clear dwell, valid HSR status when required, and an accepted operator reset?

**Required work:** Define invariants, transition guards, clock assumptions, reset semantics, and fault states. Model-check the state machine, examine simultaneous and reordered events, and generate implementation-level tests from the formal model. Explicitly distinguish properties of the mathematical core from properties of the ROS 2 executor and communications shell.

### Vector 5 — Lidar geometry and motion-envelope coverage

**Objective:** Extend the current straight corridor approximation to a validated robot footprint and motion-dependent swept volume.

**Research question:** How should the gate evaluate obstacle clearance during rotation, curved paths, reverse motion, and transitions between translation and rotation?

**Required work:** Validate scanner metadata and extrinsic transforms; derive a footprint-aware swept region; evaluate occlusion and sparse-return cases; and compare the present corridor filter against polygonal or trajectory-based collision monitors. Include explicit tests for blind forward sectors with valid lateral returns.

### Vector 6 — HSR input calibration and human-context validation

**Objective:** Establish the operational characteristics of the three HSR vectors using defined input sources and documented error rates.

**Research question:** What false-positive, false-negative, detection-delay, and recovery characteristics result when distress, isolation, and environmental-proximity signals are derived from real perception systems rather than injected simulation values?

**Required work:** Define sensor provenance, confidence calibration, temporal filtering, input-quality indicators, and uncertainty handling. Evaluate the effect of missed, delayed, contradictory, and corrupted signals. Keep HSR as an assistive contextual reflex; do not treat its current threshold logic as validated human-state perception.

---

## 8. Conclusion

QERRA-v2 Classical provides an inspectable deterministic gate core, a ROS 2 Jazzy node wrapper, a forward lidar corridor filter, an HSR telemetry input, a latched recovery contract, and node-level fault handling. The core's separation from ROS 2, explicit state inputs, integer decision units, and reproducible simulation logs provide a concrete basis for further systems-engineering evaluation.

The present evidence supports the following statements:

- The Gate Core v0.4 is implemented as a deterministic pure-function component and is covered by unit tests.
- The supervisory gate and HSR reflex behavior have been demonstrated in the specified Webots scenarios.
- The standalone `qerra_core` ROS 2 package builds and starts under ROS 2 Jazzy in GitHub Actions.
- The node publishes diagnostic state, handles the tested SIGINT lifecycle, and includes a process-lifetime tick fault latch.

The present evidence does **not** establish exclusive ROS 2 actuator authority, a physical stopping-distance guarantee, hard real-time response, hardware STO behavior, validated human-distress perception, formal safety proof, or conformity with a functional-safety standard.

The next engineering step is not to enlarge the claim. It is to close the measurable gaps: enforce the ROS authority boundary, correct the proposal timestamp and provenance contract, validate complete scan geometry, measure end-to-end latency and deceleration, and formally analyze recovery invariants.

---

## References and Implementation Records

1. D. Seto, B. H. Krogh, L. Sha, and A. Chutinan, “The Simplex Architecture for Safe On-Line Control System Upgrades,” *Proceedings of the 1998 American Control Conference*, 1998.
2. QERRA Supervisory Gate implementation: [`gate/gate_core.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/gate/gate_core.py), [`gate/gate_config.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/gate/gate_config.py), and [`gate/gate_lidar.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/gate/gate_lidar.py).
3. ROS 2 Jazzy node and HSR receiver: [`ros2/qerra_gate_node.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/ros2/qerra_gate_node.py) and [`ros2/hsr_receiver.py`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/ros2/hsr_receiver.py).
4. Safety concept and evidence anchors: [`SAFETY_CONCEPT.md`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/SAFETY_CONCEPT.md).
5. ROS 2 Jazzy CI workflow: [`.github/workflows/ros2_jazzy.yml`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/.github/workflows/ros2_jazzy.yml).
6. Python and HSR CI workflow: [`.github/workflows/tests.yml`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/.github/workflows/tests.yml).
7. Repository limitations: [`LIMITATIONS.md`](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/LIMITATIONS.md).

**Standards named as informative design references only:** ISO 13849-1, ISO 13482, and ISO 3691-4.
