# Changelog — QERRA-v2 Classical

All changes are additive. SEMEV-12 vectors are maintained as a stable core
across versions.

## [Unreleased] — Standalone ROS 2 Gate Node: Packaging, Native Jazzy CI, Fault Latch, Perception Stream Monitor, Timing Profiles and Flight Log (2026-10-30 to 2026-11-04)

Gate Core stays at v0.4. The ROS 2 node `qerra_gate_node` goes from v0.3.0 to v0.3.1, and the HSR telemetry contract (`gate/hsr_telemetry.py`) goes from v0.2.0 to v0.3.1. This section also records node work from 30 October that the 2.3.1 entry below does not cover. No release number has been assigned yet: package metadata is still 2.2.1.

Reference baselines (GitHub Actions on `main`, all passing). Counts are the author's reported results; the workflow logs are authoritative.

| Date | Commit | Test Suite run | ROS 2 Jazzy Validation run | Host unit tests (Windows) | ROS 2 node tests in the Jazzy container |
|------|--------|----------------|----------------------------|---------------------------|------------------------------------------|
| 2026-11-01 | `a7a00ba` | #742 | #7 | 192 | not recorded |
| 2026-11-03 | `fb03b85` | #760 | #25 | 197 | 19 (16 + 3) |
| 2026-11-04 | `a511d1e` | #766 | #31 | 203 | 25 (17 + 8) |

### Added
- **Standalone ROS 2 supervisory gate node (30 Oct) (`ros2/qerra_gate_node.py`, package `qerra_core`):** Wraps the pure gate core in a ROS 2 Jazzy node. Subscribes to `/cmd_vel` (`Twist`), `/scan` (`LaserScan`) and `/gate/reset` (`String`); publishes `/cmd_vel_safe` (`Twist`) and `/gate/state` (JSON `String`) on a nominal 31.25 Hz timer. The module imports without `rclpy`, so the pure logic is unit-tested on Windows.
- **Pure translators (30 Oct):** Differential-drive kinematics between `Twist` and integer wheel speeds in µrad/s (TIAGo defaults: wheel radius 0.098 m, track width 0.4044 m), with NaN and Infinity rejected. `LaserScan` to corridor returns through the existing `CorridorFilter` and `LidarPipeline`.
- **Single clock domain (30 Oct):** All node timestamps come from the ROS clock (`use_sim_time` is respected), replacing a mix of process time and message time found in review.
- **Fixed lidar geometry (30 Oct):** `lidar_n_expected` (682) and `lidar_fov_rad` (4.1887902) are startup parameters, replacing configuration from the first scan received, which made the length check compare a message with itself.
- **Packaging (30–31 Oct):** `ros2` registered in `setup.py` packages with the console script `qerra_gate_node = ros2.qerra_gate_node:main`; runtime dependencies `geometry_msgs`, `sensor_msgs` and `std_msgs` declared in `package.xml`; root `setup.cfg` placing installed scripts under `$base/lib/qerra_core`, where `ros2 run` looks; `src/qerra_msgs/package.xml` gained `<depend>action_msgs</depend>` and `<depend>service_msgs</depend>`, required by Jazzy's interface generation.
- **Node unit tests (30 Oct) (`tests/test_gate_ros2_node.py`):** Initially 8 tests covering the version and import guard, kinematics, proposal structure, NaN/Infinity rejection, the corridor filter and timestamps, a stalled sensor, and negative timestamps.
- **Node observability (31 Oct):** `/gate/state` reports `hsr_source`, `hsr_required`, `hsr_drained_total` and `hsr_socket_error`, so obstacle-only mode cannot be mistaken for the full gate.
- **Wiring tests (31 Oct) (`tests/test_gate_ros2_node_wiring.py`):** Initially 3 tests: gate parameters built the way the node builds them (matching the Webots controller's `dt_us` and `t_react_us`), a discarded scan trips a running gate, and the `/gate/state` HSR configuration fields.
- **Native ROS 2 Jazzy CI (31 Oct onward) (`.github/workflows/ros2_jazzy.yml`, "ROS 2 Jazzy Validation"):** Runs on push to `main` in the `ros:jazzy` container (Ubuntu 24.04). First run #1 on commit `7a43f9b`. The workflow builds `qerra_core` with `colcon`, confirms `qerra_gate_node` is listed by `ros2 pkg executables`, starts the installed executable from a neutral directory, captures a `/gate/state` sample with `ros2 topic echo --once`, sends SIGINT and asserts exit code 0 with no `Tick exception` in the log, and runs the node unit and wiring tests.
- **Node fault latch (1 Nov) (`NodeFaultLatch`, `tests/test_gate_ros2_node_latch.py`):** An unhandled exception in the control tick latches a node fault. The node then publishes a zero command every tick, `/gate/state` reports mode `FAULT` with `NODE_FAULT_LATCHED: <reason>`, the first reason is kept, and only a process restart clears it; `/gate/reset` does not. 6 tests.
- **Perception stream monitor with controlled rebase (3–4 Nov) (`step_hsr_stream` and `HSRStreamState` in `gate/hsr_telemetry.py`, wrapped by `ros2/hsr_receiver.py`):** Drains the raw datagrams in arrival order and checks sequence continuity before worst-severity reduction. A repeated `obs_id` sets a sticky frozen-frame fault, so the receiver presents no valid status and the gate trips `TRIP_HSR_INVALID` when HSR is required. A counter regression trips fail-closed and flushes the operating-system UDP receive buffer. After a regression the receiver accepts the new sequence only after at least 5 control ticks (at most one streak credit per tick) and at least 160,000 µs of observed duration; any `MONITOR`, `CRITICAL` or non-advancing packet resets the streak. A boundary test checks that 159 ms is rejected and 160 ms accepted. The gate core keeps its own 1.0 s continuous-clear dwell and the operator reset.
- **Timing profiles (3–4 Nov):** Node parameters `t_react_ms` (default 96.0), `lidar_period_ms` (default 32.0) and `lidar_stale_ms` (default 96.0), converted to microseconds for the gate parameters. A startup invariant, `lidar_stale_ms >= 2 * lidar_period_ms + dt_ms`, is enforced fail-closed, so the node refuses to start if it is violated. Two documented profiles: simulation (32 / 96 / 96 ms, `d_stop` 358 mm at 196 mm/s) and a 10 Hz Hokuyo URG-04LX (100 / 300 / 160 ms, `d_stop` 371 mm at 196 mm/s). The values are engineering estimates, not measurements. `/gate/state` reports `t_react_us`, `lidar_stale_us` and `lidar_period_us`.
- **Hash-chained flight log in the node (3–4 Nov):** `GateLogger` (`gate/gate_log.py`, schema v1) is integrated as `self._flight_logger` and controlled by the parameter `flight_log_path` (empty means disabled). Record 0 embeds the gate parameters and is anchored to the genesis hash. Requirement R-10: if the append or its `os.fsync()` fails, the node clamps the command to zero on the current tick and feeds `log_write_failed=True` into the gate inputs, which produces `TRIP_LOG_FAILURE`. `/gate/state` reports the trip and zero commands in the same tick. `destroy_node()` flushes and closes the file. Offline replay with `verify_log.py --replay` reproduces the recorded decisions bit-for-bit.
- **`qerra_msgs` build in CI (3 Nov):** The workflow builds the interface package with `colcon build --paths src/qerra_core src/qerra_core/src/qerra_msgs --packages-select qerra_msgs qerra_core`, then the step `Verify qerra_msgs action interface generation` compiles the `QerraEvaluate` action IDL and instantiates the generated Goal, Result and Feedback types under ROS 2 Jazzy. The action server in `ros2_bridge.py` is not run in CI.
- **Forged-input and fault-injection tests (4 Nov) (`tests/test_gate_ros2_node_wiring.py`, now 8 tests):** A reset from a source other than `operator` gives `RESET_REJECTED_CHANNEL`; a reset during the clear dwell gives `RESET_REJECTED_NOT_READY`; a reset during an obstacle breach or active distress gives `RESET_REJECTED_HAZARD`; malformed, non-JSON and causality-violating UDP packets are dropped fail-closed; a lidar beam count of 500 where 682 is expected gives `TRIP_SENSOR_INVALID`; a backward jump in simulation time gives `TRIP_CLOCK_ANOMALY`; several simultaneous hazards resolve fail-closed deterministically.

### Changed
- **Reaction-time allowance in the ROS 2 node (3–4 Nov):** The node default is 96 ms (`t_react_ms`), replacing the 32 ms Webots lockstep assumption. The Webots controller still passes 32 ms.
- **Node version:** `NODE_VERSION` is now 0.3.1.
- **HSR telemetry contract:** `gate/hsr_telemetry.py` is now v0.3.1.
- **Flight log durability (4 Nov):** `GateLogger.append()` now propagates real `os.fsync()` errors to the caller.
- **`/gate/state`:** Adds the fault fields (`fault_latched`, `fault_reason`; mode `FAULT`), the HSR configuration fields, and the timing fields listed above.

### Fixed
- **Missing `setup.cfg` (31 Oct):** CI run #2 found that `ros2 pkg executables qerra_core` printed nothing, because console scripts were installed under `bin/`. Fixed in commit `a21aabe`; run #3 passed.
- **SIGINT shutdown crash (1 Nov):** SIGINT raised `ExternalShutdownException`, and an unguarded `rclpy.shutdown()` then raised `RCLError` (exit code 1, found by CI run #4). `main()` now catches `ExternalShutdownException` and `KeyboardInterrupt` and calls `rclpy.shutdown()` only if `rclpy.ok()`. The shutdown zero-publish was removed, because it cannot work after a signal-driven shutdown; a base controller needs its own command timeout.
- **CI exit-code check (1 Nov):** A `timeout` exit status of 124 had been read as proof of a clean shutdown; it only shows that the timer fired. The workflow now starts the node in the background, sends SIGINT, waits, and asserts the real exit status.
- **Rebase dwell interval (4 Nov):** The first dwell implementation of the stream monitor had an off-by-one interval defect, now removed by requiring both the 5-tick streak and the 160 ms observed duration.
- **Test off-by-one (30 Oct) (`tests/test_synthetic_hsr_telemetry.py`):** The reset assertion now checks both ticks of the recovery: the wheels stay at zero on the `RESET_ACCEPTED` tick, and cruise speed resumes on the next `PASS` tick.

### Documentation
- `SAFETY_CONCEPT.md` v0.7 (30 Oct), v0.8 (31 Oct) and v0.9 (1 Nov): node packaging, clock and geometry hardening, HSR wiring, fault latch (AR-13, claim C-9), SIGINT lifecycle, and the open reaction-time limitation.
- `README.md`, `QERRA_FOR_ROBOTICS.md` and `QERRA-HSR-Design-v0.1.md` updated (1 Nov), including replacing "independently verified at 0.0 ms" with the same-tick reflex wording and adding the perception-boundary non-claim.
- `TECHNICAL_BRIEF_ROS2_GATE.md` added (2 Nov) and revised for commit `a511d1e` (4 Nov). It documents localhost as an assumed trusted process boundary, so a hostile local process spoofing UDP datagrams or publishing to `/cmd_vel_safe` is not defended against; mitigation belongs to operating-system permissions and SROS2.

---

## [2.3.1] - 2026-10-31 — ROS 2 Gate Node QERRA-HSR Reflex Telemetry Integration

### Added
- **Asynchronous HSR Telemetry Ingestion (`ros2/hsr_receiver.py`):** Created pure-Python, zero-`rclpy` UDP receiver on port 5008 with worst-severity batch reduction per 32 ms tick matching Webots controller parity.
- **Simulation Clock Echo (`gate_link.py`, `ros2/qerra_gate_node.py`):** Added non-blocking transmission of current ROS time on UDP port 5007 (`send_state()`), so the synthetic producer (`synthetic_hsr_producer.py`) stamps its observations in the node's clock domain.
- **Layer 1B Unit & Integration Tests (`tests/test_gate_ros2_node.py`):** Added 3 unit tests (11 tests total) verifying disabled receiver returns, UDP acute distress (`CRITICAL`) tripping to 0.0 m/s fail-closed, and `hsr_required` stale/missing heartbeat tripping. All 203 project tests pass green.

### Fixed
- **Lidar Beam Mismatch Fail-Closed Guard (`ros2/qerra_gate_node.py`):** Scans with beam counts mismatching `lidar_n_expected` (682) are immediately discarded to trip `TRIP_SENSOR_INVALID` on the next tick, preventing unhandled exceptions from terminating the subscription callback.
- **Configuration Contradiction Guard (`ros2/qerra_gate_node.py`):** Added startup validation rejecting `hsr_source="none"` when `hsr_required=True` is set, failing loudly with `ValueError`.
- **Quiescent Re-arm Verification:** Verified that `gate_core.step()` holds wheel velocity at 0.0 m/s on the `RESET_ACCEPTED` tick, resuming commanded motion on the subsequent `RUN` tick (`Reason.PASS`).

### Changed
- **Webots Reaction Parity:** Switched node parameter construction to `gate_config.get_live_gate_params` to enforce the 32 ms reaction time envelope ($t_{react} = 32\,000\ \mu\text{s}$).

---

## [2.2.1] - 2026-10-27 — Supervisory Gate & Actuator Hardening, Demo 9 Cryptographic Anchor

### Fixed
- **Gate Recovery Interlock Ordering (`gate/gate_core.py`):** Re-ordered `AWAITING_RESET` evaluation to strictly validate hazard and non-clear HSR status (`MONITOR`, `CRITICAL`, invalid, or stale) *before* accepting an operator reset, preventing premature transition to `RUN`.
- **Actuator Clamping Isolation (`tiago_supervisory_gate.py`):** Enclosed left and right motor `setVelocity(0.0)` commands in independent `try/except` blocks in `zero_wheels()`, guaranteeing that a hardware/communication fault on one motor does not abandon the other.
- **Regression Test Polish (`tests/test_gate_hsr.py`):** Configured fresh proposal sequence (`seq=2`) in `test_operator_reset_rejected_in_awaiting_reset_while_hsr_monitor` to eliminate sequence rejection warnings and isolate `RESET_REJECTED_HAZARD` as the sole event.
- **ROS 2 Package Metadata (`package.xml`):** Removed residual `<license>AGPL-3.0-only</license>` tag and bumped version to `2.2.1`, synchronizing package metadata with repository-wide Apache-2.0 relicensing.

### Added
- **Demo 9 Cryptographic Head Seal Anchor:** Formalized `results/DEMO9_SCENARIO_B_FINAL/ANCHOR.txt` locking 438 discrete simulation cycles (seal `eccb0d85416cf4a651205f34f3cc0d9275bff6e2b3baa512e4b23dbef0c2714a`) with bit-for-bit replay audit verification via `verify_log.py --replay`.
- **Actuator Clamping Safety Tests (`tests/test_controller_actuators.py`):** Added 3 unit tests verifying independent fail-closed wheel clamping when individual motor drivers encounter simulated exceptions.
- **Host Scheduling Diagnostics (`tiago_supervisory_gate.py`):** Implemented high-resolution monotonic wall-clock delta tracking between simulation steps, reporting `[HOST JITTER WARNING]` when iteration intervals reach $\ge 100\text{ ms}$ and printing timing distributions (`p50`, `p99`, `max`) at exit.

### Changed
- **Safety Concept v0.5 (`SAFETY_CONCEPT.md`):** Upgraded to Version 0.5 (Demo 9 Edition). Documented dual baseline anchors (Demo 7 and Demo 9), sub-32ms distress reflex stop (Claim C-2e), dual-dwell stabilization against spontaneous restart (Claim C-7), independent actuator clamping (AR-11, Claim C-5), and live `hsr_status` and `hsr_age_us` flight recorder fields.

---

## [2.2.0] - 2026-10-25 — Supervisory Gate & QERRA-HSR Reflex Integration (Simulation Demo 9)

### Added
- **Supervisory Gate HSR Arbitration (`gate/gate_core.py`):**
  - Integrated Layer 1B QERRA-HSR reflex companion with Layer 1A Supervisory Gate.
  - Enforced `TRIP_HSR_CRITICAL`, `TRIP_HSR_INVALID`, and `TRIP_HSR_STALE` trip reasons at the 32 ms discrete cycle boundary.
  - Added `hsr_required: bool` parameter to `GateParams` for fail-closed telemetry enforcement.
- **Flight Recorder HSR Replay (`gate/gate_log.py`, `verify_log.py`):**
  - Extended canonical flight log schema and input reconstruction to capture `hsr_status` and `hsr_stamp_us`.
  - Enables full bit-for-bit offline deterministic replay of integrated distress runs.
- **Simulation Demo 9 (Webots R2025a, PAL Robotics TIAGo base):**
  - **Scenario A (`DEMO9_SCENARIO_A_CONTROL`, 8.0 s, 250 cycles):** Causal control run proving steady cruise when distress is disabled. Head Seal: `ca2c52b3125485ab7d8724baa70d289706d419373ddfc456f950651d6b87aba1`.
  - **Scenario B (`DEMO9_SCENARIO_B_FINAL`, 14.0 s, 438 cycles):** Exercised closed-loop distress reflex stop on cycle boundary ($\le 32\text{ ms}$, cycle 125, injected confidence 0.85), active hazard reset refusal at $t = 5.024\text{ s}$, dual-dwell recovery stabilization ($1.0\text{ s}$ HSR dwell + $1.0\text{ s}$ Gate dwell), and authorized mission resumption at $t = 9.056\text{ s}$. Head Seal: `eccb0d85416cf4a651205f34f3cc0d9275bff6e2b3baa512e4b23dbef0c2714a`.
- **Environment & Controller:**
  - Added dedicated world `worlds/demo9_hsr_gate.wbt` with hospital corridor layout.
  - Configured standalone controller `controllers/tiago_supervisory_gate/tiago_supervisory_gate.py`.
- **Pre-Registration & Evidence Documentation:**
  - Added pre-registration protocol and evidence logs in `docs/demo9/PRE_REGISTRATION_D9_B.md` and `docs/demo9/DEMO9_EVIDENCE_SCENARIO_B.md`.

---

## [2.1.3] - 2026-10-23
### Changed
- Relicensed the entire repository (Supervisory Gate, SEMEV-12, THRIVE) under the **Apache License 2.0**.

---

## [2.1.2] - 2026-10-21 — Simulation Demo 8: Multi-Fault Lifecycle & Evidence Alignment

### Added
- **Simulation Demo 8 (Webots R2025a, PAL Robotics TIAGo base, `DEMO8_VIDEO_1792575455`):**
  - Documented multi-fault execution across 2,077 control cycles (66.46 s simulation time) with zero unplanned watchdog trips.
  - Exercised fail-closed lifecycle: startup latch (`TRIP_PROPOSER_DEAD`), obstacle stop (341 mm clearance vs 346 mm envelope), active hazard reset rejection (`RESET_REJECTED_HAZARD`), sensor freeze trip (`TRIP_SENSOR_INVALID` within 128 ms), proposer loss watchdog trip (`TRIP_PROPOSER_STALE` within 128 ms), and final obstacle stop (342 mm clearance vs 346 mm envelope).
  - Added sequencer controller (`controllers/tiago_demo_sequence/`) and simulation world (`worlds/demo8_supervisory_gate.wbt`).
  - Flight recorder hash chain replayed bit-for-bit against anchored external seal (`8e67456f...61cd`) using `verify_log.py --replay`.
  - Documented engineering explanations for proposer process priority mitigation (`ABOVE_NORMAL_PRIORITY_CLASS`) and LiDAR ground reflection geometry in `docs/demo8/DEMO8_YOUTUBE_TAKE.md`.

---

## [2.1.1] - 2026-10-18 — Supervisory Gate Hardening (F1–F8) & Evidence Alignment

### Added
- **F3 IPC Session Arbitration Unit Tests (`tests/test_gate_ipc.py`):**
  - Landed 5 missing unit tests checking session arbitration: default `session_id=0`, rejection of invalid types/negatives, newer session superseding older regardless of `seq`, rejection of older sessions arriving after newer, and sequence ordering within the same session. Confirmed sensitivity via 5 deliberate mutations.
- **F4 Live Reaction Time Factory (`gate/gate_config.py`):**
  - Added Webots-free parameter factory (`get_live_gate_params`) configuring justified 1-tick reaction latency ($t_{react} = 32\,000\ \mu\text{s}$).
  - Live controller (`tiago_supervisory_gate.py`) updated to use the factory, expanding the live stopping envelope at cruise speed from $339\text{ mm}$ to $346\text{ mm}$ ($+7\text{ mm}$).
  - Added `tests/test_gate_config.py` (4 tests) checking parameter values and envelope expansion.
- **F5 True Deterministic Replay (`gate/gate_log.py`, `verify_log.py`):**
  - Added `reconstruct_inputs(record)` to deserialize logged JSON inputs, properly converting JSON string infinities (`"+inf"`, `"-inf"`, `"nan"`) back to IEEE 754 floats.
  - Added `replay_log_file()` and `--replay` CLI flag to `verify_log.py` to audit that recorded outputs reproduce bit-for-bit through `gate_core.step()`.
  - Added 2 unit tests in `tests/test_gate_log.py` testing multi-tick lifecycle replay and detection of execution divergence on tampered logs.
- **V8 Harness Manifest Capture & Sealing:**
  - Added `capture_harness_manifest()` and `write_run_manifest()`.
  - Live controller writes `results/<run_id>/manifest.json` recording all injected fault switches (`QERRA_LIDAR_FAULT`, `QERRA_PROPOSER_FAULT`, fault times, `QERRA_AUTO_RESET_AT_US`, `QERRA_SMOKE_OBSTACLE`).
  - Manifest is cryptographically sealed into record 0 of the flight recorder hash chain.
- **CI Workflow Hardening (`.github/workflows/tests.yml`):**
  - Removed stale hardcoded test counts from workflow step names.
  - Added `tests/test_license_boundary.py` (4 tests) to automated CI, enforcing the Apache-2.0 / AGPL-3.0 boundary on every pull request.

### Fixed & Aligned
- **V4 Documentation:** Documented proposer wall-clock non-monotonicity, DoS integer surfaces, and trust boundary limits in `LIMITATIONS.md`.
- **V5 Documentation:** Documented in `LIMITATIONS.md` and `safety_concept.md` that the LiDAR stale watchdog is exercised exclusively by simulated fault injection and does not track physical hardware timestamps.
- **V6 Documentation:** Documented that `min_raw_lidar_returns >= 5` checks the entire 240° scan, leaving dead forward arcs with live side walls as an acknowledged boundary.
- **V7 Test Count Alignment:** Synchronized `README.md:323` and CI documentation to the exact count of **127 Unit Tests** (103 Supervisory Gate + 20 QERRA-HSR + 4 License Boundary).

---

## [2.1.0] - 2026-10-15 — Actuator Authority Separation, Decoupled Supervisory Gate, & Multi-Suite CI

### Added
- **Supervisory Gate (`gate/` v0.3):**
  - Pure-function deterministic integer state machine (`gate_core.py`) holding exclusive motor actuator authority.
  - Enforced kinematic stopping envelope $d_{stop}(v) = \lceil v^2 / (2 \cdot a_{design}) \rceil + margin$ ($a=500\text{ mm/s}^2, margin=300\text{ mm}$).
  - Enforced 150 ms proposer freshness watchdog (`t_watch_us = 150_000`) and fail-closed latched recovery requiring continuous 1.0 s clear dwell and operator reset.
  - Implemented tamper-evident SHA-256 rolling block chain flight recorder (`gate_log.py`) and standalone auditor (`verify_log.py`).
- **Simulation Demo 7 (Webots R2025a, PAL Robotics TIAGo base, `RUN_1791713619`):**
  - Demonstrated authority separation over 1,485 discrete control cycles (47.52 s sim time) with zero defects audited offline against anchored head hash `ae37ae62...c191`.
  - Commanded cruise at 2.0 rad/s (0.196 m/s); dynamic envelope bound at 339 mm; trip fired at 337 mm; standstill reached at 301 mm (36 mm coasting); cart displacement 0.0 mm.
  - Empirically confirmed `RESET_REJECTED_HAZARD` rejection when operator reset was attempted facing the cart.
- **Packaging & Portability:**
  - Registered `gate` in `setup.py` packages and `verify_log` in `py_modules`, aligned with `package.xml` at v2.1.0.
  - Implemented portable dynamic repository root discovery in `tiago_supervisory_gate.py`.

### Refactored
- **Decoupled Supervisory Gate from QERRA-HSR (`gate_core.py`):**
  - Removed `from hsr.qerra_hsr import ...` import and eliminated runtime root logging side-effects.
  - Enforced Rule AR-8 (pure standard library with zero external dependencies) and updated Rule AR-9 to direct deterministic envelope calculation ($min\_range \le d_{stop}$).
  - Added `obstacle_breach: bool` to the log record schema.

### Testing & Validation
- **Automated CI Expansion:**
  - Upgraded GitHub Actions workflow (`tests.yml`) to test all three layers in automated CI on `ubuntu-latest`.
  - Added AST inspection test (`test_gate_core_imports_stdlib_only`) confirming zero non-stdlib imports.

---

## [2.0.2] - 2026-09-28 — Layer 3 (QERRA-THRIVE) Negation Hardening & Webots Demo 6

### Added
- **Simulation Demo 6 (Compound Industrial Reflex in Webots):**
  - Modeled a compound catastrophic incident in an automotive battery assembly bay (`demo6_assembly.wbt`) using a PAL Robotics TIAGo humanoid AMR.
  - Recorded simultaneous activation of all three Layer 1 safety vectors (`immediate_physical_distress`, `human_isolation`, `environmental_hazard_proximity`).
  - Measured sub-millisecond command reflex latency (<1ms, 0.0ms delay to command `0.0 rad/s`), safe 2.9m standoff distance, and downward head inspection tilt.
  - Confirmed closed-loop enforcement of Property HSR-5: holding wheel motors fail-closed for non-interruptible payloads (`robot_task_interruptible=False`) until manual shift supervisor confirmation.
- **Universal Look-back Negation Guards across Layer 3 (QERRA-THRIVE):**
  - Deployed 40-character look-back negation detection (`HUMAN_NEGATION_GUARD` and `ECOLOGICAL_NEGATION_GUARD`) across all 12 Layer 3 vectors in Suite A and Suite B.

### Fixed
- **Suite B Negation Gap (`flora_boundary_protection`):**
  - Resolved false-positive `-0.15` intrusion penalty in Vector 10 when safe candidate actions cite avoided lawn traversal (e.g. *"avoiding driving over the lawn"*). Symmetrized negation checking with animal-startle and minimal-disturbance vectors.
- **Suite A Negation Penalties & Ranking Inversions (Vectors 1–9):**
  - Resolved ranking inversion defects where honest disclosures (e.g. *"not fully qualified"* in `transparent_disclosure`), accommodating pacings (e.g. *"will not maintain current pace"* in `balanced_pacing`), rule adaptations (`stated_preference_respect`), empowering non-takeovers (`sovereign_independence`), anti-bias disclaimers (`unbiased_perception`, `constructive_empathy`), threshold pauses (`spatial_discretion`), privacy protections (`observational_consent`), and proactive notices (`proactive_clarity`) were erroneously penalized by unnegated regex patterns.
- **Conjunction Leak in `balanced_pacing` (`PACE_REFUSAL_PATTERN`):**
  - Clause-bounded regex quantifiers using `[^,.;\s]+` to prevent the refusal pattern from leaping across commas or contrastive conjunctions (e.g. bridging *"will not [X], but will slow down"* into a false refusal to slow).

---

## [2.0.1] - 2026-09-12 — QERRA-HSR Safety Hardening & Recovery Contract

### Added
- **Human-in-the-Loop Recovery Directive (`recovery_directive`):**
  - Formally implemented the architectural intent of `robot_task_interruptible: bool` ("affects HOW, never WHETHER").
  - Added `recovery_directive: str` to `HSRResult`.
  - When `status == CLEAR`:
    - Routine task (`robot_task_interruptible=True`): `"Clear now — resume as normal."` (permits autonomous resumption).
    - Delicate/non-interruptible task (`robot_task_interruptible=False`): `"Clear now, but this was interrupted mid-task — hold for a person to confirm before continuing."` (enforces human oversight by design).
  - During active incidents (`CRITICAL` or `MONITOR`), `recovery_directive` remains silenced (`""`).
- **Injectable Clock in `StabilizedHSR`:**
  - Added dependency-injected `clock=time.monotonic` to `StabilizedHSR.__init__`.
  - Enables sub-millisecond simulated clock jumps for deterministic test harnesses and playback without relying on real-time delays.

### Fixed
- **Dwell Timer De-escalation Candidate Reset (`StabilizedHSR`):**
  - Resolved timing defect where transitioning between distinct calm levels (e.g. `CRITICAL` → `MONITOR` → `CLEAR`) retained the initial calm timestamp rather than validating the new candidate status.
  - Added `_calm_candidate_status` tracking to guarantee that a step-down to a calmer state strictly holds continuous for the full `DWELL_SECONDS` (1.0s) window.
- **Hysteresis Recovery Guard:**
  - Enforced that `StabilizedHSR` suppresses `recovery_directive` while actively dwelling in elevated states, preventing premature resumption cues before de-escalation officially completes.

---

## [2.0.0] - 2026-08-20 — Unified 3-Layer Filter-First Architecture

### Added
- **Unified 3-Layer Evaluation Pipeline (`/evaluate_pipeline`):**
  - Implemented end-to-end Filter-First pipeline connecting Layer 2 HSR (physical reflex), Layer 1 SEMEV-12 (moral filter), and Layer 3 THRIVE (action ranker).
  - Protected by an 800ms fail-closed real-time watchdog budget (`WATCHDOG_TIMEOUT_SECONDS = 0.800`).
- **Layer 3 Package (`values/`):**
  - Added QERRA-THRIVE package structure with `human_centered_suite_a` and `ecological_suite_b`.
  - Added standalone `/rank` endpoint and public `/thrive/vectors` catalog.

---

*Repository:* https://github.com/marunigno-ship-it/QERRA-v2-classical  
*Live API:* https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/docs
