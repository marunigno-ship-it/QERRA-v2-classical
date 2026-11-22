# QERRA-v2 Classical for Robotics Integration

QERRA-v2 Classical is an open-source autonomous execution firewall and supervisory guard for robot Behavior Trees, ROS 2 pipelines, and motor actuators.

It enforces a strict separation between high-level deliberation (planners, LLMs, Behavior Trees) and low-level physical actuation:
> *"Values and ethics can screen and rank what a robot wants to do, but only a deterministic gate decides what the wheels do."*

> **Status.** Early-stage research prototype. It is validated in Webots simulation and in GitHub Actions containers, not on hardware, and it is not certified. A 0.0 wheel command is a software setpoint, not an emergency stop. Localhost is treated as an assumed trusted process boundary: the gate does not defend against a hostile local process (see the security section below). See [`SAFETY_CONCEPT.md`](./SAFETY_CONCEPT.md) (v0.12) and [`LIMITATIONS.md`](./LIMITATIONS.md).

**Key strengths for robotics engineering:**
- **Deterministic Actuator Gate (Layer 1A):** Pure-function integer state machine that decides wheel commands. In the Webots controller it is the only process that writes wheel velocities. In ROS 2, `qerra_gate_node` holds designated write authority to the base controller over `/cmd_vel_safe` (ROS 2 topics do not enforce a sole publisher, so the integrator must wire the base to that topic). It enforces a dynamic stopping envelope
  $d_{stop}(v) = \lceil v^2 / (2a) \rceil + \lceil v \cdot t_{react} / 10^6 \rceil + margin$
  with $a = 500\text{ mm/s}^2$ (0.5 m/s²), $t_{react}$ in microseconds and $margin = 300\text{ mm}$. The reaction-time term is configuration-dependent: 32 ms in the Webots controller and a node parameter in ROS 2 (default 96 ms); see the timing profiles below. It also applies a 150 ms proposer freshness watchdog and fail-closed latched recovery with operator reset. Gate Core v0.5 adds optional measured-speed standstill qualification (`standstill_required: bool = False` by default, `w_standstill_tol_urad_s: int = 50_000` urad/s) that gates the 1.0 s calm dwell on physical standstill without generating a deceleration trajectory. An open-loop `TRIP_BRAKING` ramp inside the Gate was evaluated and intentionally rejected to preserve Doer-Checker separation: the Gate commands `(0, 0)` immediately upon any trip.
- **Standalone ROS 2 Gate Node:** `qerra_gate_node` (package `qerra_core`, version 0.3.1, ROS 2 Jazzy). See the section below.
- **Perception stream monitor (Layer 1B input):** A pure-function sequence monitor, `step_hsr_stream` in `gate/hsr_telemetry.py`, wrapped by the shared pure-Python receiver `gate/hsr_receiver.py` (`HsrReceiver`; `ros2/hsr_receiver.py` is a compatibility shim). It checks the order and freshness of HSR telemetry before the status reaches the gate.
- **Tamper-Evident SHA-256 Flight Recorder:** The Webots controller always appends every control cycle to an offline-verifiable rolling hash chain (`verify_log.py`). The ROS 2 node can write the same log when `flight_log_path` is set.
- **Assistive Safety Reflex (Layer 1B / QERRA-HSR):** Pure Python reflex under ISO 13482 for personal care cobots (distress, isolation, proximity) with Property HSR-5 recovery hold contracts. The Gate trips on `CRITICAL`.
- **Deterministic Moral Refusal (Layer 2 / SEMEV-12):** Evaluates 12 ethical dimensions on local CPU (~25 ms). Coercive commands trigger fail-closed stops and a physical head-shake "No" in simulation. Advisory; not part of the safety function.
- **Values Action Selection (Layer 3 / QERRA-THRIVE):** PyTrees Action Ranker selecting courteous motions (whisper transit, lawn avoidance) among already-safe actions. Advisory.
- **Simulation validated and tested:** Ten Webots demonstration scenarios on a PAL Robotics TIAGo (Demo 7 baseline: `RUN_1791713619`; Demo 9: `DEMO9_SCENARIO_B_FINAL`; Demo 10: `DEMO10_FROZEN_FRAME_20261120_125540`, 439 cycles, head seal `0250fdcb...`, replayed 439/439 cycles bit-for-bit through Gate Core v0.5). The archived Demo 7–10 runs predate v0.5 `standstill_required=True` activation, the ROS 2 timing profiles and the node flight log, so those are covered by unit tests and CI only. At the 22 Nov 2026 baseline (commit `5734dd7` prior to doc sync, package v2.4.2), the host `unittest` suite (`python -m unittest discover -s tests -p "test_*.py"`) reports **266 collected** (**252 passed**, **14 cleanly skipped without `rclpy`**, **0 failures** in 0.837 s), including `test_hsr_conformance.py` (8 tests, 28,028-case grid sweep and 24-case malformed matrix), `test_hsr_receiver_diagnostics.py` (8 tests for monotonic drop diagnostics) and `TestStandstillDwellQualification` in `test_gate_core.py`. The separate `hsr/` suite has **20 passing tests** (1.204 s); the SEMEV-12 regression has **15 cases**; the native `ros:jazzy` container has **50 passing integration tests**. GitHub Actions `tests.yml` Run #895 (1m 13s) and `ros2_jazzy.yml` Run #160 (1m 37s) are the recorded CI runs for this baseline.

---

## Standalone ROS 2 Gate Node (`qerra_gate_node`)

`qerra_gate_node` (package `qerra_core`, version 0.3.1, ROS 2 Jazzy) is a deterministic Simplex-style gatekeeper between an unverified planner and the base controller. It wraps the pure gate core (`gate_core.py` v0.5) and applies both the lidar stopping envelope (Layer 1A) and the distress reflex (Layer 1B, UDP port 5008).

```text
planner (Nav2, LLM agent, teleop) --/cmd_vel--> [ qerra_gate_node ] --/cmd_vel_safe--> base controller
                                      ^   ^   ^
                               /scan -+   |   +- HSR telemetry (UDP 5008)
                                          +- /odom (measured feedback)
```

### Interfaces

- **Subscribes:** `/cmd_vel` (`Twist`), `/scan` (`LaserScan`), `/odom` (`nav_msgs/msg/Odometry`, QoS depth 10), `/gate/reset` (`std_msgs/String`, payload `operator`). `_odom_callback()` converts the measured linear/angular twist into integer wheel speeds via `twist_to_wheel_speeds()` and stamps them at callback receipt. A 100 ms freshness and backward clock-jump watchdog (`odom_age_us < 0 or odom_age_us > 100_000`) resets the measured speeds to `None`, which blocks the recovery calm dwell when `standstill_required=True`.
- **Publishes:** `/cmd_vel_safe` (`Twist`) and `/gate/state` (`String`, JSON). The state carries the mode (`RUN`, `TRIPPED`, `AWAITING_RESET` or `FAULT`), the reason, `d_stop_mm`, the lidar minimum, the HSR status and configuration, the `standstill_required` configuration flag, the fault fields, the active timing values `t_react_us`, `lidar_stale_us` and `lidar_period_us`, and HSR diagnostics `hsr_rejected_total`, `hsr_last_rejection_reason` (sanitized fixed categories capped at 64 characters), `hsr_frozen`, `hsr_rebase_in_progress`, and `hsr_rebase_streak`.
- **UDP (localhost):** HSR telemetry is read on port 5008 (`hsr_port`). The node sends its ROS time in microseconds on port 5007 (`state_port`) so the synthetic producer stamps its observations in the node's clock domain.

| Parameter | Default | Meaning |
| --- | --- | --- |
| `rate_hz` | 31.25 | Nominal tick rate (32 ms period) |
| `hsr_source` | `udp` | `udp`, or `none` for explicit obstacle-only mode |
| `hsr_required` | true | Trip if HSR telemetry is missing, stale or invalid |
| `standstill_required` | false | Require measured wheel standstill from `/odom` for recovery calm dwell (Gate Core v0.5); defaults to false |
| `hsr_port`, `state_port` | 5008, 5007 | UDP ports for HSR datagrams and the clock echo |
| `lidar_n_expected` | 682 | Required beam count (Hokuyo URG-04LX). The Webots TIAGo lidar reports 667, so use `-p lidar_n_expected:=667` there. |
| `lidar_fov_rad` | 4.1887902 | Scan field of view, 240 degrees |
| `t_react_ms` | 96.0 | Reaction-time allowance (finite, non-negative) |
| `lidar_period_ms` | 32.0 | Assumed scan period |
| `lidar_stale_ms` | 96.0 | Scan freshness limit |
| `flight_log_path` | empty | Path of the hash-chained flight log; empty disables it |

### Stopping envelope and reaction-time profiles

At the nominal TIAGo cruise (2.0 rad/s x 98 mm wheel radius = 196 mm/s), with $a = 500\text{ mm/s}^2$ and $margin = 300\text{ mm}$:

| Configuration | `t_react` | `d_stop` at 196 mm/s | `d_stop` at 200 mm/s |
| --- | --- | --- | --- |
| Webots lockstep controller | 32 ms | 346 mm | 347 mm |
| ROS 2 simulation profile (default) | 96 ms | 358 mm | 360 mm |
| ROS 2 hardware profile, 10 Hz Hokuyo URG-04LX | 160 ms | 371 mm | 372 mm |

The node accepts three timing parameters, `t_react_ms`, `lidar_period_ms` and `lidar_stale_ms`, and refuses to start (fail-closed) unless `lidar_stale_ms >= 2 * lidar_period_ms + dt_ms`. The two profiles are:

| Profile | `lidar_period_ms` | `lidar_stale_ms` | `t_react_ms` |
| --- | --- | --- | --- |
| Simulation (default) | 32.0 | 96.0 | 96.0 |
| Physical hardware, 10 Hz Hokuyo URG-04LX | 100.0 | 300.0 | 160.0 |

The 96 ms and 160 ms values are engineering estimates of the signal chain (scan period, transport, gate tick, scheduling jitter, actuator response). They are not hardware measurements. The estimate for the hardware chain is roughly 154 to 166 ms, so 160 ms is mid-range and not an upper bound. The reaction time still has to be measured on a real chain before the envelope can support a physical stopping claim.

### Perception stream monitor

The stream monitor (`step_hsr_stream` in `gate/hsr_telemetry.py` v0.4.0, wrapped by `HsrReceiver` in `gate/hsr_receiver.py`; `ros2/hsr_receiver.py` is a compatibility shim) inspects the raw datagrams in arrival order before worst-severity reduction is applied. The v0.4.0 wire contract strictly requires all six fields—`obs_id`, `t_obs_us`, `t_emit_us`, `distress_permille`, `hazard_proximity`, and `persons_nearby_count`; missing required fields are rejected rather than supplied through fail-open defaults. `state` is optional but, when present, must match the derived classification. The packet does not carry `robot_task_interruptible` or natural-language recovery directives.

`HsrReceiver` tracks cumulative lifetime `packets_drained_total` and `packets_rejected_total`, plus the latest fixed sanitized `last_rejection_reason` category. These diagnostics are preserved monotonically across `reset()`. Rejection categories are bounded to 64 characters and do not echo untrusted wire values.

- A repeated `obs_id` latches a sticky freeze.
- A counter regression (a producer restart) trips fail-closed and starts a rebase dwell. The rebase completes only when **both** hold: at least 5 clean control ticks (`rebase_streak >= 5`, at most one credit per tick) and an observed duration of at least 160,000 µs (160 ms). Any `MONITOR`, `CRITICAL` or non-advancing packet resets the streak.
- During a fault or a rebase dwell the receiver emits `(None, None)`. With `hsr_required=true` the gate core turns that into `TRIP_HSR_INVALID` and commands 0.0 m/s.
- The gate core is unchanged by the monitor. It keeps its own 1.0 s continuous-clear dwell and still requires an explicit `operator` reset before `RUN` can return.
- **`MONITOR` semantics:** In `Mode.RUN`, `MONITOR` imposes no velocity cap in `gate_core.py`. The existing 3.0 rad/s wheel envelope at a 98 mm radius already bounds linear speed at 0.294 m/s, and person-distance information is absent from the wire packet. `MONITOR` acts fail-closed only while latched in `Mode.TRIPPED` or `Mode.AWAITING_RESET`, by blocking clear-dwell completion and rejecting operator resets (`RESET_REJECTED_HAZARD`).

The monitor protects only when `hsr_required` is true. With `hsr_required=false` the gate ignores a `None` reflex status, so counter faults do not stop the robot. The monitor detects counter faults; it cannot detect a frozen sensor behind a live producer that keeps publishing fresh counters and timestamps.

### Flight log in the node

The node integrates `GateLogger` (`gate/gate_log.py`, schema v1) through the parameter `flight_log_path` (empty string disables it). When enabled:

- Record 0 carries a manifest that embeds the gate parameters, and the chain is anchored to the genesis hash (64 zeros).
- **Requirement R-10:** if a write, flush or `os.fsync()` fails, the node clamps the command to 0.0 m/s on the current tick and `/gate/state` reports `TRIPPED` with `TRIP_LOG_FAILURE` in the same tick.
- Offline replay with `verify_log.py --replay` reproduces the recorded decisions bit-for-bit. `reconstruct_inputs()` in `gate/gate_log.py` supports deterministic replay of `proposal_invalid` while retaining backward compatibility with historical records that omit that field (it defaults to `False`). It also deserializes the optional `meas_left_urad_s` and `meas_right_urad_s` (defaulting to `None` for legacy records, verified by the 439/439 Demo 10 replay).
- The append and the `fsync` run inside the control tick, so a slow disk delays the tick without raising an error. That latency has not been measured under ROS. The head hash is not anchored anywhere outside the log.

### Fail-closed behaviour

- **Scan discard:** a scan with any beam count other than `lidar_n_expected` is discarded and the gate trips `TRIP_SENSOR_INVALID`.
- **Non-finite Twist proposal inhibition (Phase 1):** NaN or positive/negative infinity in `Twist` inputs sets `proposal_invalid=True`, emits `Event.MSG_REJECTED_INVALID`, sets `proposal_inhibited=True`, and clamps wheel output to `(0, 0)` on the Gate tick that processes the indication while remaining in `Mode.RUN`. The invalid input does not refresh the held proposal timestamp. A fresh valid finite Twist clears the temporary inhibition; otherwise the 150 ms watchdog escalates to `TRIP_PROPOSER_STALE`. This is a software command inhibition, not a physical stop.
- **Measured odometry (Gate Core v0.5):** non-finite, malformed, stale (older than 100 ms) or clock-regressed (`odom_age_us < 0`) `/odom` input resets the measured wheel speeds to `None`; with `standstill_required=True` this blocks the recovery calm dwell. The Webots controller `tiago_supervisory_gate.py` wires wheel position-sensor derivatives into `GateInputs` and defaults `QERRA_STANDSTILL_REQUIRED=1`.
- **NodeFaultLatch:** an unhandled exception in the 32 ms control tick latches a node fault. The node publishes zero every tick, `/gate/state` reports mode `FAULT` with `NODE_FAULT_LATCHED: <reason>`, and only a process restart clears it. `/gate/reset` does not. The latch does not cover exceptions in subscription callbacks.
- **Clean SIGINT shutdown:** `main()` catches `ExternalShutdownException` alongside `KeyboardInterrupt` and calls `rclpy.shutdown()` only if `rclpy.ok()`. The CI workflow asserts exit code 0. `destroy_node()` publishes no final zero command, so a base controller needs its own command watchdog.
- **Configuration guard:** startup is refused if `hsr_source="none"` and `hsr_required=true`.
- **Proposal stamping:** `Twist` has no header, so proposals are stamped at node receipt. The 150 ms watchdog therefore detects stalls at the gate, and planner compute lag is unmeasured.

### Security boundary and adversarial tests

Localhost is an assumed trusted process boundary. The UDP ports and ROS 2 topics are unauthenticated, and ROS 2 DDS does not enforce sole-publisher authority on `/cmd_vel_safe`. A hostile local process that can publish to `/cmd_vel_safe` bypasses the gate. Protection against that belongs to operating-system permissions, user separation and SROS2, outside the node.

`tests/test_adversarial_hsr.py` exercises two executable exploit scenarios:

- **Masked-distress re-arm.** If an attacker silences the genuine producer, it can forge a counter regression, a 160 ms rebase, a 1.0 s clear dwell and an operator reset, and force the gate back to `RUN` while the real distress condition persists. The robot stays inside the stopping envelope and subject to every other trip.
- **Ingestion crowding.** A burst of more than 256 datagrams per tick crowds out and delays a trailing `CRITICAL` packet across ticks.

Neither is defended against in the current design. Other tests in the suite cover forged inputs the core does refuse: a reset from a source other than `operator`, a reset during the dwell or a hazard, malformed or causality-violating UDP packets, a lidar beam-count mismatch, and a backward jump in simulation time.

### Build and run

This mirrors the current ROS 2 Jazzy CI workflow. The repository is built as the standalone package `qerra_core`; `src/qerra_msgs` is masked from colcon discovery by `src/qerra_msgs/COLCON_IGNORE` and is excluded from the root `package.xml` dependencies. `package.xml` declares `<exec_depend>nav_msgs</exec_depend>` alongside `launch` and `launch_ros`. The launch entry point `launch/qerra_gate.launch.py` exposes 15 explicitly typed node parameters through `ParameterValue` (including `standstill_required`, default `"false"`), plus six Pattern B topic-remapping arguments: `cmd_vel_in`, `cmd_vel_out`, `scan_topic`, `odom_topic` (default `/odom`), `reset_topic`, and `state_topic` (21 launch arguments in total).

```bash
source /opt/ros/jazzy/setup.bash   # Jazzy is the distro validated in CI; other distros are untested
mkdir -p ros2_ws/src && cd ros2_ws/src
git clone https://github.com/marunigno-ship-it/QERRA-v2-classical qerra_core
cd ..
rosdep install --from-paths src --ignore-src -r -y --rosdistro jazzy
colcon build --packages-select qerra_core
source install/setup.bash
ros2 launch qerra_core qerra_gate.launch.py
# Or direct execution: ros2 run qerra_core qerra_gate_node
```

Obstacle-only mode (no HSR input):

```bash
ros2 run qerra_core qerra_gate_node --ros-args -p hsr_source:=none -p hsr_required:=false
```

Hardware timing profile (10 Hz Hokuyo URG-04LX):

```bash
ros2 run qerra_core qerra_gate_node --ros-args -p lidar_period_ms:=100.0 -p lidar_stale_ms:=300.0 -p t_react_ms:=160.0
```

Optional flight log:

```bash
ros2 run qerra_core qerra_gate_node --ros-args -p flight_log_path:=/tmp/gate_audit.jsonl
```

On a fresh start the gate is latched (`TRIPPED`) until it has a valid `/scan`, a live proposer and, with the default `hsr_required=true`, a fresh HSR heartbeat. After the clear dwell, send the reset:

```bash
ros2 topic pub --once /gate/reset std_msgs/msg/String "{data: operator}"
```

### What the CI checks

The current workflow is `.github/workflows/ros2_jazzy.yml` (container `ros:jazzy`). It builds **only** the standalone `qerra_core` package with `colcon build --packages-select qerra_core`; it does not build `qerra_msgs` or instantiate the `QerraEvaluate` action interface. It verifies the installed `qerra_gate.launch.py` arguments with `ros2 launch ... --show-args`, starts the launch with live Pattern B remappings, captures `/gate/state`, verifies SIGINT shutdown (exit code 0 for the direct node check) and checks that the log contains no `Tick exception`. The lifecycle check asserts `node._standstill_required is False`. The workflow sets `QERRA_REQUIRE_ROS2="1"` for the dual-protocol and Nav2-compatible exterior test modules, so missing ROS 2 imports fail those modules rather than silently skipping them.

The workflow runs **50 container integration tests across 7 modules**: 21 in `test_gate_ros2_node.py` (including 19 translator/regression tests and the two non-finite Twist node regressions), 8 wiring/fault-injection tests (`test_gate_ros2_node_wiring.py`), 7 `/odom` ingestion and freshness-watchdog tests (`test_gate_ros2_odom.py`, using isolated ROS 2 module stubs so they execute identically on Windows and in `ros:jazzy`), 5 live DDS topic-traffic tests, 4 live dual-protocol and node-regression tests, 1 Pattern B remapping test, and 4 Nav2-compatible exterior command-interface harness tests. The 50-test total is `21 + 8 + 7 + 5 + 4 + 1 + 4`.

No live DDS `/odom` publisher test is included in the live DDS scenarios yet; the `/odom` path is covered by the stub-based tests only. The CI job does **not** launch a full Nav2 stack or `controller_server`; the Nav2-compatible exterior tests use a command-interface harness. It does not measure timing or WCET under representative load, does not build or run `qerra_msgs`, and does not test hardware.

### Known limitations

- The reaction-time values are estimates and have not been measured; the timer is Python on a general-purpose OS and jitter is unmeasured under ROS.
- The 96 ms and 300 ms scan-freshness limits are looser than the reaction budget assumes, so a scan older than the budget's single scan period can still be accepted.
- The unauthenticated channels and the two demonstrated exploit scenarios above. The `Twist` stamping caveat above.
- The stream monitor protects only with `hsr_required=true` and does not detect a frozen sensor behind a live producer.
- **ODD and threshold non-claim:** HSR thresholds (0.45/0.75 normalized, mapped to 450/750 permille, and `ISOLATION_COUNT_THRESHOLD = 1`) are author-chosen engineering placeholders. They have not been validated against any human population, posture, gait or sensor data. ODD profiles are configuration slots; only the default profile is exercised in simulation and CI. The Layer 1B packet carries no metric distance to the human subject, and no claim is made about real-distress detection, false-alarm rate or miss rate.
- **Black-channel packet-drop scope:** malformed or contradictory frames (for example, `state_mismatch`) are dropped and counted rather than immediately latching `TRIP_HSR_INVALID`. If a live producer interleaves valid `CLEAR` frames with contradictory frames, `CLEAR` remains held until valid frames cease and the 96 ms HSR staleness watchdog trips.
- **Executor assumption:** `QerraGateNode` currently relies on `SingleThreadedExecutor` serialization (`rclpy.spin(node)`) and does not use mutex locks for shared callback state. Moving callbacks into concurrent/reentrant callback groups under a `MultiThreadedExecutor` would require explicit synchronization for shared fields such as `_latest_proposal`, `_latest_ranges`, `_reset_requested`, `_meas_left_urad_s`, `_meas_right_urad_s` and `_odom_stamp_us`.
- **Rapid valid/invalid Twist chattering:** alternating `VALID -> NaN -> VALID` proposals can refresh the held proposal timestamp on each valid proposal; there is no separate chattering debounce mechanism.
- One forward corridor from one lidar; `LaserScan` metadata is not validated beyond the beam count.
- **Commanded vs measured velocity:** Gate Core v0.5 supports a standstill-qualified recovery calm dwell when `standstill_required=True`, but `d_stop` itself still uses commanded, not measured, speed. `standstill_required` defaults to `False` in `GateParams`, the ROS 2 node and the launch file. `/odom` verifies physical standstill only when it is backed by closed-loop encoders or state estimation (`open_loop=false` in `diff_drive_controller`), not under `open_loop=true` or locked-wheel skids. `/odom` uses callback receipt time (`_get_ros_time_us()`) rather than `Odometry.header.stamp`, and it is unauthenticated, so a forged standstill input is unmitigated under the localhost trust boundary. The negative-age guard (`odom_age_us < 0`) lacks a dedicated subtest in `test_gate_ros2_odom.py`, and there is no live DDS `/odom` publisher test yet.
- `Twist` only; no `TwistStamped` support.
- No hardware testing and no certification.

See the README and `SAFETY_CONCEPT.md` for the full list.

---

## Behaviour Tree Integration Pattern

QERRA operates as a Condition node evaluated before any action that involves
a human or a morally significant decision.

```
[Sequence]
 ├── [Condition]  QERRA_ethical_score < 0.5   ← safe to proceed
 ├── [Action]     ExecuteTask
 └── [Fallback]   RequestHumanReview
```

The Action Result's `decision` field maps directly to this gate:
`"safe"` = proceed, `"modified"` = action should be halted or reviewed.

---

## ROS 2 Bridge Overview

See `ros2_bridge.py` for the full implementation. The bridge is separate from `qerra_gate_node`: it exposes the advisory SEMEV-12 evaluation as an action, and it is not part of the physical safety function.

**Action:** `/qerra/evaluate` — type `qerra_msgs/action/QerraEvaluate`

**Goal:**

| Field | Type | Content |
|-------|------|---------|
| `situation_text` | `string` | Natural language situation description |
| `distress_confidence` | `float32` | QERRA-HSR signal, 0.0–1.0 |
| `persons_nearby_count` | `int32` | QERRA-HSR signal |
| `hazard_proximity_flag` | `bool` | QERRA-HSR signal |
| `robot_task_interruptible` | `bool` | QERRA-HSR signal |

**Result:**

| Field | Type | Content |
|-------|------|---------|
| `score` | `float32` | Risk score 0.0 – 1.0 |
| `decision` | `string` | `"safe"` or `"modified"` |
| `score_explanation` | `string` | Human-readable score band |
| `reasoning` | `string` | Full reasoning trace |
| `vectors_activated` | `string[]` | Activated SEMEV-12 vector IDs |
| `evaluation_source_local` | `bool` | `True` if the local CPU fallback was used |
| `success` | `bool` | Integrity flag |
| `error_message` | `string` | Populated only if `success` is `False` |

**Feedback:** `status` (`string`) — real-time updates published during evaluation.

As of the current standalone `qerra_core` packaging, `src/qerra_msgs` is masked from colcon discovery by `src/qerra_msgs/COLCON_IGNORE` and is not built or tested in the ROS 2 Jazzy Validation CI workflow; building `ros2_bridge.py` and `qerra_msgs` requires explicitly removing/bypassing `COLCON_IGNORE` in a local ROS 2 workspace.

**Running the node (rclpy required):**

```bash
source /opt/ros/jazzy/setup.bash   # Jazzy is the distro validated in CI; other distros are untested
python3 ros2_bridge.py
```

**Sending a test situation from another terminal:**

```bash
ros2 action send_goal /qerra/evaluate qerra_msgs/action/QerraEvaluate \
  "{situation_text: 'A robot is instructed to withhold information from a patient.', distress_confidence: 0.0, persons_nearby_count: 2, hazard_proximity_flag: false, robot_task_interruptible: true}"
```

The bridge also runs fully standalone with no ROS 2 installation:

```bash
python3 ros2_bridge.py   # calls the live API and prints the result
```

---

## Quick API Test (no ROS 2 needed)

```bash
curl -X POST \
  https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/analyze \
  -H "x-api-key: TEST-2026-QERRA-CLASSICAL-PUBLIC-KEY-98765" \
  -H "Content-Type: application/json" \
  -d '{"text": "A robot is ordered to restrain a patient against their will."}'
```

Expected response fields: `score` (0.0–1.0), `decision` (`safe`/`modified`),
`vectors_activated`, `reasoning`, `vector_scores`.

---

## Known Open Questions for the Robotics Community

I am actively seeking feedback from ROS 2 users and robotics engineers.
Please reply on ROS Discourse, open a GitHub issue, or email me directly.

1. **Reaction-time bounding** — The node now takes `t_react_ms`, `lidar_period_ms`
   and `lidar_stale_ms`, with a 96 ms simulation profile and a 160 ms profile for a
   10 Hz Hokuyo URG-04LX. Both are engineering estimates, not measurements. How do
   you bound this end to end (scan period, DDS queues, executor delay, base
   controller ramps), and is `ros2_tracing` the right tool for it? How should the
   scan-freshness limit relate to the reaction budget?

2. **Integration topology** — Direct remapping (planner `/cmd_vel` → gate →
   `/cmd_vel_safe` → base) or a `twist_mux` priority chain? ROS 2 does not
   enforce a sole publisher on `/cmd_vel_safe`. How do you keep other publishers
   off the safety topic in practice? The node subscribes to `Twist`, which has no
   timestamp; would you move to `TwistStamped` for a supervisor like this? Would a
   worked Nav2 example help?

3. **Lifecycle management** — I want a fail-closed latch that stays latched until
   the process is restarted. How do you represent that in a `LifecycleNode`
   without an automated lifecycle manager or respawn policy recovering the node
   and defeating the safety function?

4. **Action interface design** — Does the `QerraEvaluate` Action for the moral
   deliberation bridge (situation text + HSR signals in; score, decision,
   reasoning, and activated vectors out) fit naturally into your decision
   pipelines or Behaviour Trees? What QoS settings (Reliability, Durability,
   History depth) would you use? The bridge currently uses the ROS 2 default
   (reliable, depth 10). Early feedback favoured a dedicated action package over
   raw `std_msgs` topics, so the experimental `src/qerra_msgs` package exists in the repository (currently masked by `COLCON_IGNORE` from the standalone `qerra_core` CI build so the safety gate package stays zero-dependency).

Any input is valuable — even a short comment on one question helps shape
the next small improvements.

---

**Contact:** marunigno@gmail.com (subject: QERRA Robotics Feedback)  
**License:** Apache-2.0

*Early-stage research tool — not certified for production safety systems.*
