<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright (c) 2026 Marussa Metocharaki -->

# QERRA Supervisory Gate & Assistive Reflex (Layer 1A/1B)
## Technical Brief: Deterministic Simplex Supervision & Lifecycle Hardening for ROS 2 Mobile Robots

**Author:** Marussa Metocharaki — Independent Researcher, Solo Developer (Greece)  
 **Target Audience:** Autonomous Mobile Robot (AMR) Systems Engineers, Functional Safety Researchers, and Verification Specialists 
**Date:** November 2026 | **Document Version:** 1.0.0  
**Artifact Baseline:** `qerra_core` (Node: `qerra_gate_node` v0.3.0, Engine: Gate Core v0.4, Safety Concept v0.8)  
**Repository:** [github.com/marunigno-ship-it/QERRA-v2-classical](https://github.com/marunigno-ship-it/QERRA-v2-classical)  
**Permanent Archive (DOI):** [10.5281/zenodo.23836773](https://doi.org/10.5281/zenodo.23836773)  
**License:** Apache License 2.0  

---

### Executive Summary

Modern Autonomous Mobile Robots (AMRs) increasingly deploy high-degree-of-freedom, probabilistic software stacks—including Nav2 trajectory generators, machine-learning perception, and large language model (LLM) task agents—directly upstream of physical motor actuators. While functionally versatile, these high-complexity software layers cannot be formally verified to zero-defect certainty, are prone to runtime scheduling jitter, and can hang, drop frames, or output erratic setpoints under transient computing saturation.

This Technical Brief presents an open-source, deterministic **Simplex Supervisory Gate** implemented for **ROS 2 Jazzy Jalisco**. Operating strictly as software middleware, the architecture decouples unverified deliberation from base actuation:
1. **Layer 1A (Kinematic Supervisory Gate):** Intercepts unverified proposed velocity commands (`/cmd_vel`), evaluates forward swept lidar clearance against a dynamically computed Newtonian stopping envelope $d_{stop}(v)$, trips fail-closed within $\le 32\text{ ms}$, and enforces an unbroken $1.0\text{ s}$ calm dwell and manual operator reset before motion resumption.
2. **Layer 1B (Assistive Safety Reflex):** Ingests non-blocking UDP telemetry inspired by ISO 13482 principles to command an immediate same-tick halt upon acute human distress or environmental hazard proximity.
3. **Fault-Tolerant Node Hardening:** Incorporates an immutable, node-level runtime fault latch (`NodeFaultLatch`) and a clean `SIGINT` signal lifecycle verified natively inside Ubuntu 24.04 `ros:jazzy` Docker containers in automated CI.

> **Epistemic Honesty Boundary:** QERRA is an open-source simulation research prototype evaluated in Webots R2025a and GitHub Actions Linux containers. It is **not** a certified functional safety system. A $0.0\text{ m/s}$ command is a software setpoint delivered to motor controllers, not a hardware Safe Torque Off (STO) circuit, electro-mechanical brake coil, or emergency stop relay. References to ISO 13849-1, ISO 13482, and ISO 3691-4 are informative design references only.

---

### 1. Architectural Philosophy: The Simplex Pattern

The architecture adapts the classic **Simplex Architecture** (Lui Sha et al., Carnegie Mellon University / IEEE Computer, 1998) to modern ROS 2 mobile robotics. Rather than attempting the intractable task of formally certifying a complex navigation stack, the system splits actuation authority across an asymmetric boundary:

```text
┌────────────────────────────────────────────────────────┐
│             Unverified Complex Proposer                │
│         (Nav2, Teleoperation, Learned Policy)          │
└───────────────────────────┬────────────────────────────┘
                            │ /cmd_vel (geometry_msgs/Twist)
                            ▼
┌────────────────────────────────────────────────────────┐
│             QERRA Supervisory Gate Node                │
│                 (qerra_gate_node)                      │
│                                                        │
│  • Swept Corridor Filter (gate_lidar.py) ◄── /scan     │
│  • HSR Reflex Receiver (UDP 5008)       ◄── Telemetry  │
│  • Pure-Function Core: step(state, params, inputs)     │
│  • Node-Level Fault Latch (NodeFaultLatch)             │
└───────────────────────────┬────────────────────────────┘
                            │ /cmd_vel_safe (geometry_msgs/Twist)
                            ▼
┌────────────────────────────────────────────────────────┐
│             Low-Level Base Controller                  │
│       (diff_drive_controller / Motor Drives)           │
└────────────────────────────────────────────────────────┘
---
#### Actuator Authority Isolation Contract
- The high-level planner acts strictly as an **unverified proposer**; it is given no write access to physical base controller channels.
- The supervisory gate node (`qerra_gate_node`) holds **designated sole write authority** over `/cmd_vel_safe`. *(Topology note: ROS 2 topic namespaces are open pub/sub and do not enforce access control; physical integration requires topic remapping or secure DDS SROS2 boundaries).*
- If the planner hangs, drops frames, or crashes, the gate’s internal proposal watchdog expires ($T_{watch} = 150\text{ ms}$), clamping the output velocity setpoint to $0.0\text{ m/s}$.

---

### 2. Mathematical Stopping Envelope & Kinematics

Rather than relying on static distance thresholds, Gate Core v0.4 evaluates obstacle clearance against a dynamic kinematic envelope computed on every 32 ms tick:

$$d_{stop}(v) = \left\lceil \frac{v^2}{2 \cdot a_{design}} \right\rceil + \lceil v \cdot t_{react} \rceil + margin$$

```text

   Swept Left Margin (+0.32 m)
═══════════════════════════════════════════════════════
                   ▲
                   │   Obstacle in corridor?
 Robot [TIAGo]     │   Range <= d_stop(v)  --> TRIP_OBSTACLE
                   ▼
═══════════════════════════════════════════════════════
   Swept Right Margin (-0.32 m)
---

#### Parameter Calibration (PAL Robotics TIAGo Base Baseline)
- **Design Deceleration ($a_{design}$):** $500\text{ mm/s}^2$ ($0.5\text{ m/s}^2$).
- **Reaction Time Allowance ($t_{react}$):** $32\,000\ \mu\text{s}$ ($32\text{ ms}$, representing 1 simulation control step).
- **Standstill Margin ($margin$):** $300\text{ mm}$ ($0.30\text{ m}$ physical cushion at zero velocity).
- **Corridor Half-Width ($half\_width\_m$):** $0.32\text{ m}$ ($0.27\text{ m}$ base half-width + $0.05\text{ m}$ lateral clearance).

#### Example Calculation at Nominal Cruise
For a commanded linear velocity $v = 0.196\text{ m/s}$ ($2.0\text{ rad/s}$ wheel speed on $r = 0.098\text{ m}$ wheels):
1. **Braking Distance Term:** $\lceil 0.196^2 / (2 \times 0.5) \rceil = \lceil 0.0384 \rceil \to \mathbf{39\text{ mm}}$
2. **Reaction Distance Term:** $\lceil 0.196 \times 0.032 \rceil = \lceil 0.0063 \rceil \to \mathbf{7\text{ mm}}$
3. **Static Margin:** $\mathbf{300\text{ mm}}$
4. **Total Active Stopping Envelope:** $d_{stop} = 39 + 7 + 300 = \mathbf{346\text{ mm}}$

#### Lidar Pipeline & Fail-Closed Integrity (`gate_lidar.py`)
- Ingests raw `sensor_msgs/msg/LaserScan` arrays and filters returns across the $0.64\text{ m}$ forward swept corridor, masking non-path lateral returns to $+\infty$.
- **Geometry Guard:** Default hardware profile expects $682$ beams across a $240^\circ$ FOV (Hokuyo URG-04LX). A scan arriving with any divergent length is discarded immediately, setting internal buffers to `None` and forcing the gate to trip fail-closed (`TRIP_SENSOR_INVALID`).

---text

### 3. State Machine & Recovery Contracts

The core decision engine (`gate_core.py`) is structured as a **pure mathematical function with zero side effects**:
$$\text{step}(\text{GateState}, \text{GateParams}, \text{GateInputs}) \longrightarrow \text{StepResult}(\text{GateState}, \text{Record}, \text{LeftSpeed}, \text{RightSpeed})$$

All state transitions are deterministic and completely decoupled from system wall clocks (timestamps are passed in as explicit microsecond inputs):

```text
                  ┌────────────────────────┐
                  │          RUN           │
                  └───────────┬────────────┘
                              │ Trip Condition (Obstacle, Stale, HSR, Fault)
                              ▼
                  ┌────────────────────────┐
                  │        TRIPPED         │◄─────┐
                  └───────────┬────────────┘      │ Hazard Re-detected /
                              │ 1.0s Calm Dwell   │ Transient Glitch
                              ▼                   │
                  ┌────────────────────────┐      │
                  │     AWAITING_RESET     │──────┘
                  └───────────┬────────────┘
                              │ Valid Operator Reset (/gate/reset)
                              ▼
                  ┌────────────────────────┐
                  │    RESET_ACCEPTED      │
                  │ (Quiescent 0.0 m/s)    │
                  └───────────┬────────────┘
                              │ Next Tick (inputs clear)
                              ▼
                  ┌────────────────────────┐
                  │          RUN           │
                  └────────────────────────┘
#### Fail-Closed Trip Triggers
1. `TRIP_OBSTACLE`: Swept corridor minimum range $\le d_{stop}(v)$.
2. `TRIP_PROPOSER_DEAD` / `TRIP_PROPOSER_STALE`: Proposal age $\ge 150\text{ ms}$.
3. `TRIP_SENSOR_INVALID`: Scan length mismatch, NaN/Inf, blind array ($< 5$ valid returns), or frozen timestamp.
4. `TRIP_HSR_CRITICAL`: Acute distress detected over Layer 1B telemetry.
5. `TRIP_HSR_STALE` / `TRIP_HSR_INVALID`: Reflex heartbeat missing or age $> 96\text{ ms}$ ($3 \times dt$).
6. `TRIP_CLOCK_ANOMALY`: Non-monotonic timestamp regression.

#### Recovery Contract: Anti-Chattering Dwell & Quiescent Re-arm
- **Anti-Chattering Stabilization (Hazard H-06):** To prevent spontaneous restart or high-frequency chattering when an obstacle hovers at the threshold, recovery requires an unbroken $1.0\text{ s}$ ($1\,000\,000\ \mu\text{s}$) calm dwell window. Any transient hazard detection immediately resets the dwell timer.
- **Explicit Operator Authorization:** Once in `AWAITING_RESET`, motion will not resume autonomously. An explicit operator message (`/gate/reset = "operator"`) is mandatory. Reset requests while hazards persist are strictly rejected (`RESET_REJECTED_HAZARD`).
- **Quiescent Re-arm Tick:** On the exact cycle an operator reset is accepted (`RESET_ACCEPTED`), wheel commands are held clamped at $0.0\text{ m/s}$ (preventing sudden physical lurching upon reset). Forward motion resumes only on the subsequent nominal `RUN` cycle (`Reason.PASS`).

---

### 4. ROS 2 Node Hardening & Fault Latching

In wrapping Gate Core v0.4 into an operational ROS 2 node (`ros2/qerra_gate_node.py`), specific architectural mechanisms were implemented to address runtime failure modes:

#### Node-Level Fault Latch (`NodeFaultLatch`)
- Standard ROS nodes typically trap runtime exceptions in try-catch blocks and log an error while continuing to spin. In a supervisory safety gate, an unhandled exception inside a control tick represents a compromise of the safety kernel.
- If any unhandled Python exception occurs within `_tick_callback`, `self._fault_latch.trip(exc)` triggers:
  1. The latch locks into an immutable `True` state for the process lifetime.
  2. The root-cause exception string is recorded and preserved (subsequent faults cannot overwrite the initial root cause).
  3. Every subsequent timer tick short-circuits execution, publishing a $0.0\text{ m/s}$ zero Twist.
  4. Diagnostic state JSON on `/gate/state` forces `"mode": "FAULT"`, `"reason": "NODE_FAULT_LATCHED: <exc>"`, and clamps commanded speeds to zero.
  5. Recovery strictly requires an external process termination and restart; topic-level `/gate/reset` messages cannot clear the latch.

#### Clean POSIX Signal Lifecycle & Context Shutdown
- In ROS 2 Jazzy, external process termination (`kill -INT` / SIGINT) causes `rclpy.spin()` to raise `rclpy.executors.ExternalShutdownException`.
- The node traps `(KeyboardInterrupt, ExternalShutdownException)`, bypasses invalid publishing on an inactive context, and guards `if rclpy.ok(): rclpy.shutdown()`, preventing pybind11 context crashes (`RCLError`) and guaranteeing clean process exit code 0.

---

### 5. Empirical Evidence & Verification Baseline

Claims are categorized using strict epistemic status vocabulary:
- **SPECIFIED:** Documented in design; unbuilt.
- **IMPLEMENTED:** Code complete; unit-tested without ROS.
- **VERIFIED:** Proven by live simulation telemetry with cryptographic hash seals or reproducible automated CI logs.

| Claim | Target Mechanism | Evidence Status | Proof Baseline & Measurement |
|---|---|---|---|
| **C-1: Authority Separation** | Proposer isolated on unprivileged IPC; Gate owns output channel. | **VERIFIED** | Run `RUN_1791713619` (Webots TIAGo): Proposer isolated on UDP 5005; gate owns motor handles. |
| **C-2a: Obstacle Trip & Coasting** | Commanded clamp to $0.0\text{ m/s}$ within $\le 32\text{ ms}$ upon envelope breach. | **VERIFIED** | Run `RUN_1791713619`: Trip fired at $337\text{ mm}$ clearance; standstill reached at $301\text{ mm}$ ($36\text{ mm}$ physical coasting). Obstacle cart undisplaced at $X = 2.8\text{ m}$. |
| **C-2e: Acute Reflex Clamp** | Commanded clamp to $0.0\text{ m/s}$ within $\le 32\text{ ms}$ upon Layer 1B `CRITICAL`. | **VERIFIED** | Run `DEMO9_SCENARIO_B_FINAL`: Distress injected at $t = 4.000\text{ s}$ (Cycle 125); clamped to $0.000\text{ rad/s}$ on exact cycle boundary (0 added latency ticks). |
| **C-3: Tamper-Evident Flight Log** | Rolling SHA-256 hash chain ($hash_i = \text{SHA256}(hash_{i-1} + \text{canonical\_bytes}_i)$). | **VERIFIED** | Run `RUN_1791713619` (1,485 cycles, seal `ae37...`) and `DEMO9_SCENARIO_B_FINAL` (438 cycles, seal `eccb...`). Verified bit-for-bit offline via `verify_log.py --replay`. |
| **C-6: Guarded Recovery Contract** | Rejection of reset during active hazard or active distress. | **VERIFIED** | Run `DEMO9_SCENARIO_B_FINAL`: Reset refused at $t = 5.024\text{ s}$ during active distress (`RESET_REJECTED_HAZARD`). Dwell completion verified at $t = 9.056\text{ s}$ before reset accepted. |
| **C-7b: Gate-Level Clear Dwell** | Independent Gate-level verification of continuous fresh HSR `CLEAR`. | **IMPLEMENTED** | Covered by 8 dedicated unit tests in `tests/test_gate_hsr_clear_dwell.py`. |
| **C-8: Ratchet Re-basing** | Recovery from malformed sequence numbers upon proposal age expiry. | **IMPLEMENTED** | Covered by 7 dedicated unit tests in `tests/test_gate_ratchet_rebase.py`. |
| **Node Fault Latch** | Permanent fail-closed latching upon unhandled tick exception. | **IMPLEMENTED** | Covered by 6 dedicated unit tests in `tests/test_gate_ros2_node_latch.py`. |
| **Jazzy Native Execution** | Colcon build, neutral directory execution, and SIGINT exit 0. | **VERIFIED** | GitHub Actions Run #7 (Commit `a7a00ba`, container `ros:jazzy`): Passed in 43s; exit code 0 asserted. |

#### Master Test Suite Counts (as of November 2026)
- **ROS 2 Node Unit/Wiring Tests (`tests/test_gate_ros2_node*.py`):** 20 tests passing (11 translator/HSR integration, 6 fault latch, 3 node wiring).
- **Host Unit Test Discovery (`tests/test_*.py`):** 192 tests passing in 2.05s.
- **Physical Safety Reflex Suite (`hsr/`):** 20 tests passing (14 activation cases, 6 hysteresis stabilizer tests).
- **GitHub Actions Linux CI Test Suite:** 206+ tests passing.

---

### 6. Epistemic Limits & Safety Honesty Boundaries

To prevent technical over-claiming, the following boundaries are formally stated:

1. **Simulation-to-Reality Reaction Time Gap ($t_{react}$):**
   The current stopping distance envelope uses $t_{react} = 32\text{ ms}$, derived directly from the Webots discrete lockstep simulation tick. In physical deployments, total reaction latency includes physical sensor acquisition (nominal ~100 ms for a 10 Hz Hokuyo URG-04LX), Linux kernel scheduling, DDS network deserialization, and motor driver ramp-down latency. The physical stopping distance $d_{stop}$ is therefore **optimistic** until empirically measured on target hardware.
2. **Software Setpoint vs. Emergency Stop:**
   A commanded velocity of $0.0\text{ m/s}$ is a numerical software setpoint transmitted to a base controller. It does not replace, nor approximate, certified Safe Torque Off (STO) relays, mechanical brake coils, or dual-channel safety PLCs required under ISO 3691-4.
3. **Execution Environment Determinism:**
   Python running on general-purpose Ubuntu Linux cannot provide hard real-time execution guarantees. Garbage collection pauses and CPU scheduling jitter can introduce execution variance under heavy system load.
4. **Unauthenticated Boundaries:**
   ROS 2 topic `/gate/reset` and localhost UDP port 5008 operate without cryptographic sender authentication; local privilege separation assumes a secure, isolated OS runtime.
5. **No Runtime Perception Classification:**
   Distress signals in simulation demonstrations are synthetically injected by test harnesses; no claim of validated real-time visual distress perception is made.

---

### 7. Concrete Research & Collaboration Vectors 

The architectural foundation of QERRA is stable, open-source, and verified in continuous integration. Collaboration with physical robotics research laboratories and mobile robot verification groups is sought across five specific systems-engineering vectors:

#### Vector 1: Empirical Reaction-Time Bounding via `ros2_tracing`
- **Objective:** Replace the $32\text{ ms}$ simulation assumption with statistically bounded, measured latency distributions on physical AMR platforms.
- **Research Question:** Using LTTng and `ros2_tracing`, what is the p99 and worst-case execution time (WCET) across the complete physical chain:
  $$\text{Lidar Packet Arrival} \longrightarrow \text{IP Stack} \longrightarrow \text{RCL Executor Dispatch} \longrightarrow \text{Gate Evaluation} \longrightarrow \text{diff\_drive\_controller}$$

#### Vector 2: HIL Benchmarking Against `nav2_collision_monitor`
- **Objective:** Establish a fair, reproducible comparative benchmark between Nav2's native polygon collision monitor and QERRA's Simplex supervisory gate.
- **Research Question:** Using recorded hardware rosbag replays of corridor incursions, how do dynamic polygon slowdowns compare against deterministic state-latching with calm dwell recovery in terms of mechanical brake wear, chattering avoidance, and passenger/pedestrian comfort?

#### Vector 3: Integration Topologies (`twist_mux` vs. Direct Remap)
- **Objective:** Formulate standardized safety topology guidelines for ROS 2 navigation pipelines.
- **Research Question:** Does positioning the supervisory gate as an input into a standard `twist_mux` priority chain introduce unacceptable priority inversion risks, or should the supervisory gate sit exclusively downstream of all multiplexers as an inline filter before the base controller?

#### Vector 4: Formal Lifecycle State Machine Modeling
- **Objective:** Harmonize fail-closed state latching with standard `rclpy.lifecycle.LifecycleNode` conventions.
- **Research Question:** How can a persistent, fail-closed state latch (requiring physical manual investigation) be represented within standard ROS 2 lifecycle states without an external, automated lifecycle manager inadvertently triggering an uninspected transition back to `Active`?

#### Vector 5: Assistive Cobot Safety Verification (ISO 13482)
- **Objective:** Evaluate Layer 1B assistive reflex contracts (human distress, isolation, and task-interruptibility recovery directives) in physical healthcare and shared-workspace cobot trials.

---

### Contact & Artifact Repositories

- **Lead Developer:** Marussa Metocharaki (Independent Solo Developer)
- **Location:** Greece | **Email:** `marunigno@gmail.com`
- **Core Repository:** `https://github.com/marunigno-ship-it/QERRA-v2-classical`
- **Authoritative Technical Documentation:**
  - Complete README & Build Instructions: `README.md`
  - Formal Safety Concept & Invariants: `SAFETY_CONCEPT.md` (v0.8/v0.9)
  - Full Framework Architecture: `CURRENT_ARCHITECTURE.md`
