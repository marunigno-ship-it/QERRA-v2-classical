# Changelog — QERRA-v2 Classical

SEMEV-12 vectors are maintained as a stable core across versions. This log
records additions, changes, fixes and retired integration paths.

## [2.5.0] - 2026-11-28 — Measured-Velocity Stopping Envelope, Sensor Integrity & Empirical ROS 2 Timing Baseline

### Added
- **Measured-Velocity Stopping Envelope (`gate/gate_core.py`):** Hardened dynamic stopping envelope calculation to $d_{\text{stop}}(v) = \lceil v_{\text{ref}}^2 / (2 \cdot a_{\text{design}}) \rceil + \lceil v_{\text{ref}} \cdot t_{\text{react}} / 10^6 \rceil + margin$ with $v_{\text{ref}} = \max(v_{\text{cmd}}, v_{\text{meas}})$. Forward chassis translational speed ($v_{\text{meas}}$) is derived from measured wheel feedback via `chassis_forward_mmps()`, preventing stopping envelope collapse during uncommanded chassis coasting. Covered by `TestMeasuredVelocityStoppingEnvelope` in `tests/test_gate_core.py`.
- **Mathematical Invariant Verification (`tests/test_gate_invariants.py`):** Implemented pure Python standard-library property-based invariant test suite executing >117,000 state transitions across Layer 1A and Layer 1B state machines with zero invariant violations.
- **ROS-Native Topic Telemetry & Pattern B Launch (`ros2/`, `launch/`):** Added ROS-native topic subscription (`/hsr/telemetry`) to `gate/hsr_receiver.py` (operating with zero open UDP sockets in topic mode). Added 21-parameter launch file `launch/qerra_gate.launch.py` supporting Pattern B exterior command interceptor remapping (`cmd_vel_in`, `cmd_vel_out`, `odom_topic`, `scan_topic`, `reset_topic`, `state_topic`).
- **10-Point LaserScan Metadata Validation (`ros2/qerra_gate_node.py`):** Added `validate_laserscan_metadata()` pure-Python physical invariant checklist verifying headers, beam counts, ordered angle bounds, field-of-view tolerances, center alignment, and non-negative range limits. Discards invalid scans to fail closed (`TRIP_SENSOR_INVALID`).
- **REP-117 Physical Range Bounds (`gate/gate_lidar.py`):** Implemented strict `range_min` and `range_max` bounds enforcement. Forward corridor returns $< \text{range\_min}$ convert to NaN (tripping `TRIP_SENSOR_INVALID`); lateral returns $< \text{range\_min}$ mask to $+inf$; returns $> \text{range\_max}$ are excluded from raw valid points and masked to $+inf$. Verified by 27 unit & callback tests in `tests/test_gate_ros2_laserscan_metadata.py`.
- **Empirical Timing Baseline & Contention Benchmarks (`tools/`):** Added `tools/bench_gate_core.py` (100k CPU microbenchmark) and `tools/bench_ros2_executor.py` (6-scenario SingleThreadedExecutor benchmark measuring platform noise floor, gate compute jitter, active traffic contention, synchronous SHA-256 flight log `os.fsync()` overhead, synthetic head-of-line blocking, and separate-process hazard trip software response over 100 seeded randomized trials). Added manual CI workflow `.github/workflows/timing.yml`.
- **Nav2 Coexistence Architecture:** Formulated and documented the Simplex-inspired layered command topology (`Nav2 Controller -> Nav2 Collision Monitor -> QERRA Gate -> Base Controller`).

### Changed
- **Version Metadata Bumps:** Bumped package version to `2.5.0` in `package.xml` and `setup.py`. Bumped ROS 2 gate node version to `0.3.2` in `ros2/qerra_gate_node.py`.
- **Documentation Alignment:** Synchronized `LIMITATIONS.md` with Phase 4 empirical timing metrics and updated LaserScan metadata validation status. Synchronized `README.md` test counts (319 host / 80 container tests across 8 modules) and release metadata.

### Testing & Validation
- **Host Test Suite (Windows 11):** 319 tests passed, 16 cleanly skipped on hosts lacking `rclpy` (0 failures).
- **ROS 2 Jazzy Container Suite (`ros:jazzy`):** 80 tests passing across 8 modules in GitHub Actions CI.
- **Empirical Timing Benchmark Run (Azure VM Ubuntu 24.04, `rmw_fastrtps_cpp`, Python 3.12.3):**
  * Nominal compute p99 $\le 1.051\text{ ms}$ under active 682-beam traffic and synchronous SHA-256 flight logging; 0 missed deadlines (>35 ms).
  * Monotonic expected-release lateness ($t_0 + k \times 32\text{ ms}$) max $< 0.89\text{ ms}$.
  * Head-of-line blocking demonstration (40 ms injected scan pause): 99/99 missed deadlines, 903.199 ms cumulative schedule slip.
  * Scenario 6 separate-process obstacle trip latency over 100 seeded trials: $\text{p50} = 16.227\text{ ms}$, $\text{p95} = 31.705\text{ ms}$, $\text{max} = 32.348\text{ ms}$ (software response only; 100/100 verified exact zero Twist and correlated `TRIP_OBSTACLE`).

---

## [2.4.2] - 2026-11-22 — Verified Standstill Qualification, Odometry Ingestion & Gate Hardening (Gate Core v0.5)

### Added
- **Verified Standstill Qualification (`gate/gate_core.py`):** Hardened the Supervisory Gate recovery lifecycle to resolve the "Standstill Dwell Trap." Added immutable `standstill_required: bool = False` (default for backward compatibility) and `w_standstill_tol_urad_s: int = 50_000` (tolerance $\le 0.05\text{ rad/s} \approx 4.9\text{ mm/s} on 98 mm wheels) to `GateParams`. Added `meas_left_urad_s: Optional[int]` and `meas_right_urad_s: Optional[int]` to `GateInputs`. In `Mode.TRIPPED`, the 1.0 s calm dwell timer strictly requires confirmed physical standstill before arming.
- **Mid-Dwell Motion Reset Guard (`gate/gate_core.py`):** Implemented fail-closed dwell resetting. If physical chassis motion exceeding tolerance is detected while dwelling in `Mode.TRIPPED` (e.g. external collision, rolling on slopes, or caster sliding), `clear_since_us` resets to `None` immediately, enforcing continuous standstill before transition to `AWAITING_RESET`.
- **Standstill Core Unit Test Suite (`tests/test_gate_core.py`):** Added `TestStandstillDwellQualification` (4 tests) covering dwell inhibition during physical coasting, dwell activation upon standstill, mid-dwell motion reset, and missing feedback fail-closed handling. All 65 core unit tests pass green.
- **ROS 2 Odometry Integration (`ros2/qerra_gate_node.py`):** Subscribed to `/odom` (`nav_msgs/msg/Odometry`), translating body linear/angular twist to integer wheel speeds via `twist_to_wheel_speeds()`. Added `DEFAULT_ODOM_STALE_US` (100 ms) staleness watchdog and clock-regression protection (`odom_age_us < 0 or odom_age_us > DEFAULT_ODOM_STALE_US` fails closed to `None`). Exposed `standstill_required` parameter and updated `/gate/state` diagnostic JSON.
- **ROS 2 Odometry Ingestion Test Suite (`tests/test_gate_ros2_odom.py`):** Added 7 standalone tests running `_odom_callback` and `_tick_callback` against isolated ROS 2 stubs. Verifies exact integer translation across straight, spin, arc, standstill, and reverse twists; 100 ms freshness ceiling; NaN/Inf rejection; malformed message rejection; and recovery after fault. Tests run on Windows without ROS 2 installed.
- **Webots Wheel Sensor Telemetry (`controllers/tiago_supervisory_gate/tiago_supervisory_gate.py`):** Converted PAL Robotics TIAGo wheel position sensor derivatives into integer $\mu\text{rad/s}$ and wired them directly into `GateInputs(meas_left_urad_s=..., meas_right_urad_s=...)`. Added `QERRA_STANDSTILL_REQUIRED` environment configuration (defaults to `1` in live simulation).

### Changed
- **Version Metadata Bumps:** Bumped `GATE_CORE_VERSION` to `0.5` in `gate/gate_core.py`. Synchronized `package.xml` and `setup.py` to `2.4.2`.
- **Flight Recorder Input Reconstructor (`gate/gate_log.py`):** Updated `reconstruct_inputs()` to deserialize `meas_left_urad_s` and `meas_right_urad_s` with `.get(...)` fallbacks, guaranteeing 100% backward compatibility with older flight logs.

### Testing & Validation
- **Full Discovery Test Suite:** 215 host tests collected under `tests/`; 201 passed, 14 cleanly skipped on Windows without `rclpy` (100% pass rate in 0.997s).
- **Cryptographic Replay Audit:** Historical Demo 10 audit log (`results/DEMO10_FROZEN_FRAME_20261120_125540/gate_audit.jsonl`) replayed 439/439 discrete control cycles bit-for-bit with 0 divergence against anchored head seal `0250fdcbff64af691dc52f5d60a89305d691ce3ca6b662281e7e9c73ff46437a`.

---
## [Unreleased] — Standalone ROS 2 Gate Node: Packaging, Native Jazzy CI, Fault Latch, Perception Stream Monitor, Timing Profiles, Flight Log, Adversarial Verification, Live DDS Traffic, Dual-Protocol Watchdogs, Launch Configuration, Pattern B Remapping, Node Regressions & CI Isolation (2026-10-30 to 2026-11-15)

### Current branch baseline — 15 November 2026

The current verified `main` baseline is commit `be45e4c`. The standalone ROS 2
package `qerra_core` is at package version `2.4.1` (ROS package format 3,
`ament_python`, Apache-2.0). The repository's Git tag list is currently empty;
`2.4.1` is package metadata on `main`, not a tagged release. Gate Core remains
v0.4, the ROS 2 node `qerra_gate_node` remains v0.3.1, and the HSR telemetry
contract (`gate/hsr_telemetry.py`) remains v0.3.1.

`qerra_core` is built as a standalone package. The experimental
`src/qerra_msgs` subtree is masked by `src/qerra_msgs/COLCON_IGNORE`, is not a
`qerra_core` dependency in the root `package.xml`, and is excluded from the
current `ros2_jazzy.yml` build. The earlier `qerra_msgs` interface-generation
experiment is historical; it is not part of the current package build or
release boundary.

### Verified CI and test baseline

Both GitHub Actions workflows passed on commit `be45e4c` on 15 November 2026.
The run identifiers and durations below identify the current verified runs;
the test output in each workflow is the authority for the reported counts.

| Date | Commit | Test Suite run | ROS 2 Jazzy Validation run | Host suite under `tests/` | ROS 2 Jazzy container suite |
|------|--------|----------------|----------------------------|---------------------------|-----------------------------|
| 2026-11-01 | `a7a00ba` | #742 | #7 | 192 | not recorded |
| 2026-11-03 | `fb03b85` | #760 | #25 | 197 | 19 (16 + 3) |
| 2026-11-04 | `a511d1e` | #766 | #31 | 203 | 25 (17 + 8) |
| 2026-11-05 | `docs(sc)` | #773 | #31 | 211 | 25 (17 + 8) |
| 2026-11-07 | `test(ros2)` | #781 | #50 | 215 (211 pass, 4 skip) | 29 (17 + 8 + 4) |
| 2026-11-08 | `ci(ros2)` | #790 | #56 | 217 (211 pass, 6 skip) | 31 (17 + 8 + 4 + 2) |
| 2026-11-10 | `ci(jazzy)` | #802 | #68 | 218 (211 pass, 7 skip) | 32 (17 + 8 + 4 + 2 + 1) |
| 2026-11-11 | `ci(nav2)` | #808 | #75 | 222 (211 pass, 11 skip) | 36 (17 + 8 + 4 + 2 + 1 + 4) |
| **2026-11-15** | **`be45e4c`** | **#834 — passed (1 min 6 s)** | **#99 — passed (1 min 4 s)** | **230 collected: 217 passed, 13 skipped, 0 failed** | **40 passed (19 + 8 + 4 + 4 + 1 + 4)** |

The 13 host skips are expected on Windows without `rclpy`: 4 live-traffic
tests, 4 dual-protocol/node-regression tests, 1 remapping test, and 4
Nav2-compatible exterior tests. The separate `hsr/` suite contributes another
20 passing tests in Test Suite run #834; these 20 tests are not included in
the 230-test `tests/` host count.

The 40 native Jazzy container tests are distributed as follows:

| Test module | Tests | Coverage |
|---|---:|---|
| `tests/test_gate_ros2_node.py` | 19 | 17 existing node/translator tests plus the 10 Hz `dt_us` scaling and post-reset HSR phase-sweep regressions |
| `tests/test_gate_ros2_node_wiring.py` | 8 | Node wiring, parameter construction, forged-input and fault-injection cases |
| `tests/test_gate_ros2_live_traffic.py` | 4 | Live DDS traffic and Layer 1A watchdog scenarios |
| `tests/test_gate_ros2_dual_protocol.py` | 4 | 2 live DDS/UDP dual-protocol tests plus 2 actual `QerraGateNode` regressions |
| `tests/test_gate_ros2_remapping.py` | 1 | Pattern B topic remapping |
| `tests/test_gate_ros2_nav2_exterior.py` | 4 | Nav2-compatible exterior command-interface harness |
| **Total** | **40** | **Native `rclpy` execution in `ros:jazzy`** |

The 2 new tests in `test_gate_ros2_node.py` are
`test_10hz_dt_us_scales_max_tick_gap_and_allows_dwell_recovery` and
`test_hsr_receiver_post_reset_continuity_across_40ms_and_50ms_phases`. The HSR
test sweeps every 1 ms phase offset for nominal 40 ms and 50 ms UDP periods
across `RESET_ACCEPTED`. The 2 node regressions in
`test_gate_ros2_dual_protocol.py` verify actual `QerraGateNode` 10 Hz parameter
propagation and that an accepted reset preserves the receiver's state.

### Added

- **Rate-scaled Gate Core timing regression coverage (15 Nov) (`tests/test_gate_ros2_node.py`):** Added a pure-Python 10 Hz parameter/dwell regression. With `dt_us=100_000`, `max_tick_gap_us` is `200_000` (2 × `dt_us`), and a continuous dwell remains valid across nominal 100 ms ticks. Added an actual-node regression in `tests/test_gate_ros2_dual_protocol.py` to verify that `QerraGateNode` propagates its `rate_hz`-derived `self._dt_us` into `get_live_gate_params()`.
- **HSR post-reset continuity regression coverage (15 Nov) (`tests/test_gate_ros2_node.py`, `tests/test_gate_ros2_dual_protocol.py`):** Added a pure-Python `HsrReceiver`/`step()` phase sweep across 40 ms and 50 ms UDP producer periods, testing every 1 ms phase offset across `RESET_ACCEPTED`. Added an actual ROS-node regression verifying that the accepted-reset path preserves `HsrReceiver` state. This protects against a phase-dependent false `TRIP_HSR_INVALID` on the first `RUN` tick for HSR streams slower than the 31.25 Hz gate tick.
- **CI process and DDS isolation checks (15 Nov) (`.github/workflows/ros2_jazzy.yml`):** Added per-step `ROS_DOMAIN_ID` isolation using IDs 11–18 so tests and launch processes do not discover traffic from other workflow steps. Added explicit `pkill -9 -f "[q]erra_gate_node"` cleanup after launch/executable steps and a follow-up process check. A remaining `<defunct>` process entry is distinguished from a live node process; the check is intended to ensure no active orphaned gate node contaminates later tests.
- **Linux adversarial UDP flood-test socket sizing (15 Nov) (`tests/test_adversarial_hsr.py`):** Set `SO_RCVBUF` to `1_048_576` on the flood-test socket, before `bind()`, with `OSError` handling. This prevents the Linux default receive-buffer limit (approximately 208 KB on the tested runner) from dropping datagrams before the test's `HsrReceiver` can drain the 261-packet burst. This is a test-harness buffer adjustment, not a change to the production HSR receiver's bounded-drain policy.
- **Nav2-compatible exterior command-interface integration test suite (Priority P12) (11 Nov) (`tests/test_gate_ros2_nav2_exterior.py`, `.github/workflows/ros2_jazzy.yml`):** Added a four-test multi-node DDS suite using native `rclpy` in `ros:jazzy`. It checks linear cruise through `/cmd_vel_nav` to `/base/cmd_vel`, an active default-topic isolation canary, coordinated Twist arc passthrough, obstacle interception, and proposer-stream interruption. The harness does not launch a Nav2 `controller_server`; the isolation canary is bounded to the test's observation window and is not proof of graph-wide publisher exclusivity.
- **Live ROS 2 topic traffic and watchdog suite (7 Nov) (`tests/test_gate_ros2_live_traffic.py`):** Added four native DDS tests covering clear-corridor dwell and operator reset, cruise and obstacle clamping, scan-loss handling, hazard-time reset refusal, and proposer timeout.
- **Live dual-protocol integration suite (Priority P10) (8 Nov; expanded 15 Nov) (`tests/test_gate_ros2_dual_protocol.py`):** Initially added two tests running DDS topics concurrently with HSR UDP telemetry on port 5008. The module now contains four tests: the original live dual-protocol distress and stale-heartbeat scenarios, plus two ROS-gated `QerraGateNode` regressions for 10 Hz timing propagation and accepted-reset HSR receiver continuity.
- **Pattern B live topic remapping integration test (Priority P11) (10 Nov) (`tests/test_gate_ros2_remapping.py`):** Added a native Jazzy multi-node test verifying node-specific remapping of the proposal, scan and output topics, cruise passthrough, obstacle clamping and default-topic isolation for the tested configuration.
- **Standard ROS 2 launch entry point and typed launch interface (9–11 Nov; completed 15 Nov) (`launch/qerra_gate.launch.py`):** Added the installed `qerra_gate.launch.py` entry point with five topic-remapping arguments and all 14 node parameters explicitly typed using `ParameterValue`. The 14 parameters are `rate_hz`, `track_width_m`, `wheel_radius_m`, `robot_half_width_m`, `lidar_n_expected`, `lidar_fov_rad`, `t_react_ms`, `lidar_period_ms`, `lidar_stale_ms`, `hsr_source`, `hsr_port`, `hsr_required`, `state_port`, and `flight_log_path`.
- **Standalone ROS 2 supervisory gate node (30 Oct) (`ros2/qerra_gate_node.py`, package `qerra_core`):** Wrapped the pure Gate Core in a ROS 2 Jazzy node. The node subscribes to `/cmd_vel`, `/scan` and `/gate/reset`, publishes `/cmd_vel_safe` and `/gate/state`, polls HSR UDP telemetry, and optionally writes a hash-chained flight log. Its default timer rate is 31.25 Hz. The module keeps pure translation logic importable and testable on hosts without `rclpy`.
- **Pure Twist and scan translators (30 Oct):** Added differential-drive conversion between `Twist` and integer wheel speeds in µrad/s (TIAGo defaults: wheel radius 0.098 m, track width 0.4044 m), plus conversion of `LaserScan` data through `CorridorFilter` and `LidarPipeline`. Non-finite Twist values are rejected by the translator; the node-level hold-last-valid consequence is documented below under limitations.
- **Node fault latch (1 Nov) (`NodeFaultLatch`, `tests/test_gate_ros2_node_latch.py`):** Added a process-lifetime latch for unhandled exceptions in the control tick. The node publishes a zero software Twist setpoint and reports `mode="FAULT"` with `NODE_FAULT_LATCHED`; `/gate/reset` cannot clear the latch, and process restart is required.
- **Perception stream monitor with controlled rebase (3–5 Nov) (`step_hsr_stream`, `HSRStreamState`, `ros2/hsr_receiver.py`):** Added arrival-order sequence validation before worst-severity reduction. Repeated `obs_id` values latch a frozen-frame fault. A counter regression enters rebase dwell requiring both at least five control-tick credits and at least 160,000 µs of producer-observation duration. `MONITOR`, `CRITICAL` or non-advancing packets reset the streak.
- **Timing profiles and startup invariant guard (3–5 Nov; rate scaling completed 15 Nov) (`ros2/qerra_gate_node.py`):** Added `t_react_ms`, `lidar_period_ms` and `lidar_stale_ms` parameters and the fail-closed startup invariant `lidar_stale_ms >= 2 * lidar_period_ms + dt_ms`. The node's `dt_us` is derived from `rate_hz` and passed to `get_live_gate_params()`; `max_tick_gap_us` scales as `2 * dt_us` rather than remaining fixed at 64,000 µs. This is 64,000 µs at 31.25 Hz (`dt_ms=32`) and 200,000 µs at 10 Hz (`dt_ms=100`). The default-rate simulation profile is `lidar_period_ms=32`, `lidar_stale_ms=96`, `t_react_ms=96` (configured `d_stop=358 mm` at 196 mm/s); the 10 Hz scanner profile is `100 / 300 / 160 ms` (configured `d_stop=371 mm` at 196 mm/s). These scanner profiles use the default 31.25 Hz gate loop unless `rate_hz` is separately changed. At a 10 Hz gate loop with a 100 ms lidar period, the startup check is `300 >= 2 × 100 + 100`; the 10 Hz loop regression verifies parameter propagation and dwell continuity, not a physical or real-time performance bound.
- **Hash-chained flight log in the node (3–5 Nov) (`gate/gate_log.py`, `ros2/qerra_gate_node.py`):** Integrated schema-v1 `GateLogger` through `flight_log_path`. Record 0 embeds the gate parameters and harness manifest; an append or `os.fsync()` error clamps the software command to zero on the current tick and reports `TRIP_LOG_FAILURE`. Offline `verify_log.py --replay` checks bit-for-bit decision reproduction.
- **Historical experimental `qerra_msgs` interface work (3 Nov; no longer part of the current build):** The `QerraEvaluate` action interface was previously compiled and its generated Goal, Result and Feedback types instantiated under Jazzy. This experiment is retained in the repository history only; as of 15 Nov, `src/qerra_msgs` is masked by `COLCON_IGNORE` and excluded from the standalone `qerra_core` build.
- **Stream monitor edge-case matrix suite (5 Nov) (`tests/test_hsr_stream_matrix.py`):** Added six tests for interleaved producers, timestamp/counter ordering, stuttering frames, mid-dwell distress, intra-batch regressions and timestamp stagnation.
- **Executable adversarial exploit tests (5 Nov) (`tests/test_adversarial_hsr.py`):** Added two executable demonstrations of unauthenticated-localhost limits: masked-distress re-arm by a process able to silence the genuine producer and forge recovery traffic, and ingestion crowding where a burst exceeding the bounded 256-datagram drain delays a trailing `CRITICAL` packet across ticks.
- **Forged-input and fault-injection tests (4 Nov) (`tests/test_gate_ros2_node_wiring.py`):** Expanded the wiring suite to eight tests covering reset-source validation, reset refusal during dwell or hazard, malformed/non-JSON UDP input, lidar beam-count mismatch, clock reversal and deterministic multi-hazard resolution.

### Changed

- **Package version and standalone package boundary (15 Nov) (`package.xml`, `setup.py`, `src/qerra_msgs/COLCON_IGNORE`, `.github/workflows/ros2_jazzy.yml`):** Synchronized `qerra_core` package metadata in `package.xml` and `setup.py` to `2.4.1`. The root package remains format 3, `ament_python`, Apache-2.0. Removed `qerra_msgs` from the root package dependencies, added/retained `src/qerra_msgs/COLCON_IGNORE` to mask that subtree, and excluded it from the Jazzy build. Package version `2.4.1` is not yet represented by a Git tag.
- **AR-2 reverse-command clamping (15 Nov) (`gate/gate_core.py`, `LIMITATIONS.md`):** Documented AR-2 Option A with `w_min_urad_s = 0`: if either wheel proposal is negative, both wheel outputs are clamped symmetrically to `(0, 0)`. This is a command-envelope clamp, not a separate trip. No clamp Event is emitted. Consequently, `/gate/state` may report `mode="RUN"`, `reason="PASS"` and an empty `events` list while `cmd_left_urad_s` and `cmd_right_urad_s` report the clamped zero commands. `Reason.PASS` means no trip fired on that tick; it does not guarantee unclamped passthrough.
- **Rate-dependent dwell continuity (15 Nov) (`ros2/qerra_gate_node.py`, `gate/gate_config.py`):** Corrected the node to store the timer period derived from `rate_hz` as `self._dt_us` and pass `dt_us=self._dt_us` to `get_live_gate_params()`. The resulting `max_tick_gap_us` is `2 * dt_us`: 64,000 µs at the default 31.25 Hz (32 ms) and 200,000 µs at 10 Hz (100 ms). This fixes dwell continuity when the node is configured below its default rate.
- **Complete typed launch parameter exposure (15 Nov) (`launch/qerra_gate.launch.py`):** Confirmed that all 14 node parameters are exposed through typed `ParameterValue` declarations, including kinematic parameters `track_width_m` (0.4044 m), `wheel_radius_m` (0.098 m), `robot_half_width_m` (0.32 m), `lidar_fov_rad`, and `state_port`, as well as timing, lidar, HSR and flight-log parameters. The five topic-remapping arguments remain available: `cmd_vel_in`, `cmd_vel_out`, `scan_topic`, `reset_topic`, and `state_topic`.
- **Launch runtime dependencies (11 Nov) (`package.xml`):** Declared `<exec_depend>launch</exec_depend>` and `<exec_depend>launch_ros</exec_depend>` for the installed launch entry point. The package also declares its pytest test dependency.
- **HSR producer freshness boundary (15 Nov) (`gate/gate_config.py`, `ros2/hsr_receiver.py`, `LIMITATIONS.md`):** Documented the default HSR freshness threshold of 96,000 µs (96 ms). A 10 Hz producer has 100 ms nominal packet intervals and therefore exceeds the freshness threshold during a nominal interval. A producer rate of at least 20 Hz (interval no greater than 50 ms) is the practical nominal minimum for this configuration. This is not a physical latency guarantee; jitter, queuing and processing delay can still cause a packet to become stale.
- **Accepted-reset HSR receiver continuity (15 Nov) (`ros2/qerra_gate_node.py`):** Removed the receiver reset previously performed immediately after `RESET_ACCEPTED`. The gate's `hsr_dwell_ok` condition has already required one second of unbroken fresh `CLEAR` frames. Preserving the receiver's existing stream state avoids clearing `_last_status` and `_stream_state` to `None`, which could cause a phase-dependent `TRIP_HSR_INVALID` on the first `RUN` tick for slower-than-31.25 Hz HSR streams. The receiver continues to enforce the 96 ms freshness threshold.
- **CI workflow ROS graph isolation and process cleanup (15 Nov) (`.github/workflows/ros2_jazzy.yml`):** Assigned distinct `ROS_DOMAIN_ID` values 11–18 per workflow step to isolate DDS discovery. Added explicit post-launch/executable cleanup with `pkill -9 -f "[q]erra_gate_node"` and a leftover-process check to prevent an orphaned launch child from contaminating a later test. Both `tests/test_gate_ros2_dual_protocol.py` and `tests/test_gate_ros2_nav2_exterior.py` enforce `QERRA_REQUIRE_ROS2="1"`, so missing ROS 2 imports fail in the Jazzy job rather than silently turning those integration tests into skips.
- **CI shutdown checks (10–15 Nov) (`.github/workflows/ros2_jazzy.yml`):** The workflow sends SIGINT to the launch parent first and uses bounded escalation/cleanup. A successful workflow run verifies the scripted process lifecycle and cleanup checks; it does not establish a hardware stop or guarantee that every possible process failure is safe.
- **LiDAR subscription QoS (7 Nov) (`ros2/qerra_gate_node.py`):** Uses `qos_profile_sensor_data` (Best Effort, Volatile) for `/scan` to interoperate with the intended sensor-data publisher profile.
- **`/gate/state` diagnostics (7–15 Nov):** Retains the `events` list and reports node/gate versions, mode, reason, clamped wheel commands, HSR status and receiver diagnostics, fault-latch state, proposal age/sequence, and active timing parameters. AR-2 clamping does not currently create a separate Event.
- **Node and HSR software versions:** `NODE_VERSION` remains `0.3.1`; the HSR telemetry contract remains `0.3.1`; Gate Core remains `v0.4`.

### Fixed

- **`dt_us` propagation into live gate parameters (15 Nov) (`ros2/qerra_gate_node.py`):** Fixed an omission where the node calculated and validated its timer period from `rate_hz` but did not pass that period to `get_live_gate_params()`. At 10 Hz, the core now receives `dt_us=100_000` and derives `max_tick_gap_us=200_000`, preserving the intended dwell-continuity tolerance.
- **Post-reset HSR false re-trip (15 Nov) (`ros2/qerra_gate_node.py`):** Removed the post-`RESET_ACCEPTED` call to `HsrReceiver.reset()`. The one-second fresh-CLEAR dwell has already established continuity; retaining receiver state prevents the next tick from interpreting the cleared receiver state as missing/invalid telemetry solely because a valid UDP packet has not arrived within that 32 ms phase.
- **Linux UDP flood-test packet loss (15 Nov) (`tests/test_adversarial_hsr.py`):** Increased the test socket's receive-buffer request to 1 MiB before binding, with `OSError` handling, so Linux's default socket receive buffer does not discard packets in the test burst before the receiver drains them. This corrects test determinism, not the production 256-datagram drain limit.
- **Rebase dwell interval (4 Nov):** Corrected an off-by-one interval defect by requiring both a five-tick streak and 160 ms of observed duration.
- **SIGINT shutdown crash (1 Nov):** `main()` catches `ExternalShutdownException` and `KeyboardInterrupt` and calls `rclpy.shutdown()` only when `rclpy.ok()`.
- **Missing `setup.cfg` (31 Oct):** Console scripts install under `$base/lib/qerra_core`, where `ros2 run` discovers them.
- **Quiescent reset-tick test (30 Oct) (`tests/test_synthetic_hsr_telemetry.py`):** Verified that wheel outputs remain zero on `RESET_ACCEPTED` and motion may resume on the next eligible `RUN` tick.

### Known behaviour and retained limitations

- **Non-finite Twist proposals (15 Nov) (`ros2/qerra_gate_node.py`, `gate/gate_core.py`):** `twist_to_proposal()` rejects NaN/Inf values with `ValueError`. `_cmd_vel_callback()` logs the rejection and sets `_latest_proposal = None`. The core treats an absent new proposal as no update and retains `state.held`; therefore the previously accepted non-zero command may remain the held command until the proposer watchdog expires at `t_watch_us = 150_000` and produces `TRIP_PROPOSER_STALE`. This path is not an immediate zero-command stop. It remains a documented limitation for a later explicit fail-closed policy decision.
- **AR-2 diagnostic semantics (15 Nov):** The symmetrical `(0, 0)` reverse clamp is reflected in the published wheel-command fields but does not currently emit a dedicated Event. `PASS` reports that no trip fired, not that the proposal passed through unchanged.
- **HSR timing (15 Nov):** The default 96 ms freshness threshold does not support nominal 10 Hz / 100 ms HSR producers. At least 20 Hz is the practical nominal producer-rate boundary for the current threshold, not a guarantee under jitter or end-to-end delays.
- **ROS 2 actuator authority:** Topic remapping remains configuration, not publisher authentication or exclusive base-controller access control. The Nav2-compatible exterior tests use a harness and do not instantiate an actual Nav2 stack.
- **Software stop and hardware boundary:** A zero `Twist` is a software velocity setpoint, not an emergency stop, mechanical brake or hardware STO. No physical robot tests, functional-safety certification, PL/SIL claim or standards conformity are implied by green CI.

### Testing & Validation

- **Host suite (15 Nov):** 230 tests collected under `tests/`; 217 passed, 13 cleanly skipped on Windows without `rclpy`, and 0 failed. The 13 expected skips comprise 4 live-traffic tests, 4 dual-protocol/node-regression tests, 1 remapping test and 4 Nav2-compatible exterior tests.
- **HSR suite (15 Nov):** 20 tests passed separately under `hsr/` in Test Suite workflow run #834; they are not included in the 230 host `tests/` count.
- **Native ROS 2 Jazzy suite (15 Nov):** 40 tests passed in the official `ros:jazzy` container: 19 node tests + 8 wiring tests + 4 live-traffic tests + 4 dual-protocol/node-regression tests + 1 remapping test + 4 Nav2-compatible exterior tests.
- **GitHub Actions evidence (15 Nov, commit `be45e4c`):** `QERRA-v2 Classical Test Suite` (`tests.yml`) run #834 passed in 1 min 6 s; `ROS 2 Jazzy Validation` (`ros2_jazzy.yml`) run #99 passed in 1 min 4 s.
- **ROS 2 import enforcement:** `tests/test_gate_ros2_dual_protocol.py` and `tests/test_gate_ros2_nav2_exterior.py` both enforce `QERRA_REQUIRE_ROS2="1"` in the Jazzy environment; a ROS import failure is an error rather than a silent skip in these modules.
- **Historical suite evolution:** The 11 November baseline was 222 host tests (211 passed, 11 skipped) and 36 Jazzy tests. The 15 November baseline supersedes those counts; historical entries in the table above are retained for traceability.

### Documentation

- **`TECHNICAL_BRIEF_ROS2_GATE.md` updated to document 1.4.0 (15 Nov):** Updated the software baseline to `qerra_core` 2.4.1 on commit `be45e4c`, corrected the standalone package boundary, test evidence and 14-parameter launch interface, and documented rate-scaled `dt_us`, AR-2 symmetrical clamping, HSR freshness/rate boundary, post-reset receiver continuity and the non-finite Twist hold-last-valid behaviour.
- **`LIMITATIONS.md` synchronized to v2.4.1 (15 Nov):** Documented AR-2 Option A symmetrical `(0, 0)` clamping while retaining the historical stationary-wheel wording; added the 96 ms HSR freshness/20 Hz practical producer-rate boundary and the non-finite Twist hold-last-valid limitation.
- **Safety-concept comparison note in `TECHNICAL_BRIEF_ROS2_GATE.md` (15 Nov):** Updated the brief's comparison note to identify `qerra_core` Release v2.4.1 on `main`. The cited `SAFETY_CONCEPT.md` baseline remains v0.10; this documentation alignment does not change the Gate Core version or claim safety certification.
- **Earlier documentation updates (5–7 Nov):** `SAFETY_CONCEPT.md` v0.10 records the stream monitor, timing profiles, flight-log failure response, node fault latch and adversarial boundaries. `QERRA_FOR_ROBOTICS.md`, `QERRA-HSR-Design-v0.1.md` and `README.md` were updated for the earlier ROS 2 integration and test baselines; their earlier dates/counts remain historical snapshots.

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
