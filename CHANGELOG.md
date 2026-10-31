# Changelog — QERRA-v2 Classical

All changes are additive. SEMEV-12 vectors are maintained as a stable core
across versions.

## [2.3.1] - 2026-10-31 — ROS 2 Gate Node QERRA-HSR Reflex Telemetry Integration

### Added
- **Asynchronous HSR Telemetry Ingestion (`ros2/hsr_receiver.py`):** Created pure-Python, zero-`rclpy` UDP receiver on port 5008 with worst-severity batch reduction per 32 ms tick matching Webots controller parity.
- **Simulation Clock Echo (`gate_link.py`, `ros2/qerra_gate_node.py`):** Added non-blocking transmission of current ROS time on UDP port 5007 (`send_state()`), enabling external perception stress-testing scripts (`synthetic_hsr_producer.py`) to synchronize observation timestamps without drift.
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
