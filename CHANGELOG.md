# Changelog — QERRA-v2 Classical

All changes are additive. SEMEV-12 vectors are maintained as a stable core
across versions.

---

## [2.1.1] - 2026-10-18 — Supervisory Gate Hardening (F1–F8) & Evidence Alignment

### Added
- **F3 IPC Session Arbitration Unit Tests (`tests/test_gate_ipc.py`):**
  - Landed 5 missing unit tests verifying session arbitration: default `session_id=0`, rejection of invalid types/negatives, newer session superseding older regardless of `seq`, rejection of older sessions arriving after newer, and sequence ordering within the same session. Verified sensitivity via 5 deliberate mutations.
- **F4 Live Reaction Time Factory (`gate/gate_config.py`):**
  - Added Webots-free parameter factory (`get_live_gate_params`) configuring justified 1-tick reaction latency ($t_{react} = 32\,000\ \mu\text{s}$).
  - Live controller (`tiago_supervisory_gate.py`) updated to use the factory, expanding the live stopping envelope at cruise speed from $339\text{ mm}$ to $346\text{ mm}$ ($+7\text{ mm}$).
  - Added `tests/test_gate_config.py` (4 tests) verifying parameter values and envelope expansion.
- **F5 True Deterministic Replay (`gate/gate_log.py`, `verify_log.py`):**
  - Added `reconstruct_inputs(record)` to deserialize logged JSON inputs, properly converting JSON string infinities (`"+inf"`, `"-inf"`, `"nan"`) back to IEEE 754 floats.
  - Added `replay_log_file()` and `--replay` CLI flag to `verify_log.py` to audit that recorded outputs reproduce bit-for-bit through `gate_core.step()`.
  - Added 2 unit tests in `tests/test_gate_log.py` verifying multi-tick lifecycle replay and detection of execution divergence on tampered logs.
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
- **V7 Test Count Alignment:** Synchronized `README.md:323` and CI documentation to the exact verified count of **127 Unit Tests** (103 Supervisory Gate + 20 QERRA-HSR + 4 License Boundary).

---

## [2.1.0] - 2026-10-15 — Actuator Authority Separation, Decoupled Supervisory Gate, & Verified Multi-Suite CI

### Added
- **Supervisory Gate (`gate/` v0.3):**
  - Pure-function deterministic integer state machine (`gate_core.py`) holding exclusive motor actuator authority.
  - Enforced kinematic stopping envelope $d_{stop}(v) = \lceil v^2 / (2 \cdot a_{design}) \rceil + margin$ ($a=500\text{ mm/s}^2, margin=300\text{ mm}$).
  - Enforced 150 ms proposer freshness watchdog (`t_watch_us = 150_000`) and fail-closed latched recovery requiring continuous 1.0 s clear dwell and operator reset.
  - Implemented tamper-evident SHA-256 rolling block chain flight recorder (`gate_log.py`) and standalone auditor (`verify_log.py`).
- **Simulation Demo 7 (Webots R2025a, PAL Robotics TIAGo base, `RUN_1791713619`):**
  - Demonstrated authority separation over 1,485 discrete control cycles (47.52 s sim time) with zero defects verified offline against anchored head hash `ae37ae62...c191`.
  - Commanded cruise at 2.0 rad/s (0.196 m/s); dynamic envelope bound at 339 mm; trip fired at 337 mm; standstill reached at 301 mm (36 mm coasting); cart displacement 0.0 mm.
  - Empirically verified `RESET_REJECTED_HAZARD` rejection when operator reset was attempted facing the cart.
- **Packaging & Portability:**
  - Registered `gate` in `setup.py` packages and `verify_log` in `py_modules`, aligned with `package.xml` at v2.1.0.
  - Implemented portable dynamic repository root discovery in `tiago_supervisory_gate.py`.

### Refactored
- **Decoupled Supervisory Gate from QERRA-HSR (`gate_core.py`):**
  - Removed `from hsr.qerra_hsr import ...` import and eliminated runtime root logging side-effects.
  - Enforced Rule AR-8 (pure standard library with zero external dependencies) and updated Rule AR-9 to direct deterministic envelope calculation ($min\_range \le d_{stop}$).
  - Added `obstacle_breach: bool` to the log record schema.

### Testing & Verification
- **Automated CI Expansion:**
  - Upgraded GitHub Actions workflow (`tests.yml`) to test all three layers in automated CI on `ubuntu-latest`.
  - Added AST inspection test (`test_gate_core_imports_stdlib_only`) proving zero non-stdlib imports.

---

## [2.0.2] - 2026-09-28 — Layer 3 (QERRA-THRIVE) Negation Hardening & Webots Demo 6

### Added
- **Simulation Demo 6 (Compound Industrial Reflex in Webots):**
  - Modeled a compound catastrophic incident in an automotive battery assembly bay (`demo6_assembly.wbt`) using a PAL Robotics TIAGo humanoid AMR.
  - Verified simultaneous activation of all three Layer 1 safety vectors (`immediate_physical_distress`, `human_isolation`, `environmental_hazard_proximity`).
  - Proved sub-millisecond command reflex latency (<1ms, 0.0ms delay to command `0.0 rad/s`), safe 2.9m standoff distance, and downward head inspection tilt.
  - Verified closed-loop enforcement of Property HSR-5: holding wheel motors fail-closed for non-interruptible payloads (`robot_task_interruptible=False`) until manual shift supervisor confirmation.
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
  - Resolved timing defect where transitioning between distinct calm levels (e.g. `CRITICAL` → `MONITOR` → `CLEAR`) retained the initial calm timestamp rather than verifying the new candidate status.
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
