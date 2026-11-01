# QERRA-v2 Classical for Robotics Integration

QERRA-v2 Classical is an open-source autonomous execution firewall and supervisory guard for robot Behavior Trees, ROS 2 pipelines, and motor actuators.

It enforces a strict separation between high-level deliberation (planners, LLMs, Behavior Trees) and low-level physical actuation:
> *"Values and ethics can screen and rank what a robot wants to do, but only a deterministic gate decides what the wheels do."*

> **Status.** Early-stage research prototype. It is validated in Webots simulation and in GitHub Actions containers, not on hardware, and it is not certified. A 0.0 wheel command is a software setpoint, not an emergency stop. See [`SAFETY_CONCEPT.md`](./SAFETY_CONCEPT.md) and [`LIMITATIONS.md`](./LIMITATIONS.md).

**Key strengths for robotics engineering:**
- **Deterministic Actuator Gate (Layer 1A):** Pure-function integer state machine that decides wheel commands. In the Webots controller it is the only process that writes wheel velocities. In ROS 2, `qerra_gate_node` holds designated write authority to the base controller over `/cmd_vel_safe` (ROS 2 topics do not enforce a sole publisher, so the integrator must wire the base to that topic). It enforces a dynamic stopping envelope
  $d_{stop}(v) = \lceil v^2 / (2a) \rceil + \lceil v \cdot t_{react} \rceil + margin$
  with $a = 0.5\text{ m/s}^2$ (500 mm/s²), $t_{react} = 32\text{ ms}$ (32,000 µs) and $margin = 300\text{ mm}$, giving $d_{stop} = 346\text{ mm}$ at cruise 2.0 rad/s (0.196 m/s). It also applies a 150 ms proposer freshness watchdog and fail-closed latched recovery with operator reset.
- **Standalone ROS 2 Gate Node:** `qerra_gate_node` (package `qerra_core`, version 0.3.0, ROS 2 Jazzy). See the section below.
- **Tamper-Evident SHA-256 Flight Recorder:** The Webots controller appends every control cycle to an offline-verifiable rolling hash chain (`verify_log.py`). The ROS 2 node does not write this log yet.
- **Assistive Safety Reflex (Layer 1B / QERRA-HSR):** Pure Python reflex under ISO 13482 for personal care cobots (distress, isolation, proximity) with Property HSR-5 recovery hold contracts. The Gate trips on `CRITICAL`.
- **Deterministic Moral Refusal (Layer 2 / SEMEV-12):** Evaluates 12 ethical dimensions on local CPU (~25 ms). Coercive commands trigger fail-closed stops and a physical head-shake "No" in simulation. Advisory; not part of the safety function.
- **Values Action Selection (Layer 3 / QERRA-THRIVE):** PyTrees Action Ranker selecting courteous motions (whisper transit, lawn avoidance) among already-safe actions. Advisory.
- **Simulation validated and tested:** Nine Webots demonstration scenarios on a PAL Robotics TIAGo (Demo 7 baseline: `RUN_1791713619`). In the last local run (1 Nov 2026): 192 unit tests in `tests/` (these include the 20 ROS 2 node translator, HSR receiver, wiring and fault-latch tests) and 20 in `hsr/`, plus the 15-case SEMEV-12 regression script. GitHub Actions runs the Python 3.10 suite and the `ROS 2 Jazzy Validation` workflow on every push to `main`; those runs are the source of truth for current counts.
---

## Standalone ROS 2 Gate Node (`qerra_gate_node`)

`qerra_gate_node` is a deterministic Simplex-style gatekeeper between an unverified planner and the base controller. It wraps the pure gate core (`gate_core.py` v0.4) and applies both the lidar stopping envelope (Layer 1A) and the distress reflex (Layer 1B, UDP port 5008).

```text
planner (Nav2, LLM agent, teleop) --/cmd_vel--> [ qerra_gate_node ] --/cmd_vel_safe--> base controller
                                       ^   ^
                                /scan -+   +- HSR telemetry (UDP 5008)
```

- **Subscribes:** `/cmd_vel` (`Twist`), `/scan` (`LaserScan`), `/gate/reset` (`std_msgs/String`, payload `operator`).
- **Publishes:** `/cmd_vel_safe` (`Twist`), `/gate/state` (`String`, JSON: mode, reason, `d_stop_mm`, lidar minimum, HSR status and configuration, fault fields).
- **Fail-closed scan discard:** the expected beam count is a fixed parameter (`lidar_n_expected`, default 682 for a Hokuyo URG-04LX; the Webots TIAGo lidar reports 667, so set `-p lidar_n_expected:=667` for that simulation). A scan with any other beam count is discarded and the gate trips `TRIP_SENSOR_INVALID`.
- **NodeFaultLatch:** an unhandled exception in the 32 ms control tick latches a node fault. The node publishes zero every tick, `/gate/state` reports mode `FAULT` with `NODE_FAULT_LATCHED: <reason>`, and only a process restart clears it. `/gate/reset` does not.
- **Clean SIGINT shutdown:** `main()` catches `ExternalShutdownException` alongside `KeyboardInterrupt` and calls `rclpy.shutdown()` only if `rclpy.ok()`. The CI workflow asserts exit code 0. The node does not publish a final zero command on shutdown, so a base controller needs its own command timeout.
- **Configuration guard:** startup is refused if `hsr_source="none"` and `hsr_required=true`.

Build and run (mirrors the CI workflow, where the repository is the package `qerra_core`):

```bash
source /opt/ros/jazzy/setup.bash   # Jazzy is the distro validated in CI; other distros are untested
mkdir -p ros2_ws/src && cd ros2_ws/src
git clone https://github.com/marunigno-ship-it/QERRA-v2-classical qerra_core
cd ..
rosdep install --from-paths src --ignore-src -r -y --rosdistro jazzy
colcon build --packages-select qerra_core
source install/setup.bash
ros2 run qerra_core qerra_gate_node
```

Obstacle-only mode (no HSR input):

```bash
ros2 run qerra_core qerra_gate_node --ros-args -p hsr_source:=none -p hsr_required:=false
```

On a fresh start the gate is latched (`TRIPPED`) until it has a valid `/scan`, a live proposer and, with the default `hsr_required=true`, a fresh HSR heartbeat. After the clear dwell, send the reset:

```bash
ros2 topic pub --once /gate/reset std_msgs/msg/String "{data: operator}"
```

**What the CI checks** (`.github/workflows/ros2_jazzy.yml`, container `ros:jazzy`): the package builds and the executable is discoverable; the installed executable starts from a neutral directory under real `rclpy`; a `/gate/state` sample is captured; SIGINT gives exit code 0 and the log contains no `Tick exception`; the node unit and wiring tests run in the container.

**What it does not check:** real `/cmd_vel` and `/scan` traffic, the reset path, timing under load, anything on hardware, and the `qerra_msgs` package (it is not built in CI).

**Known limitations:** `t_react = 32 ms` is the Webots lockstep assumption, so `d_stop` is optimistic for a real robot until the reaction time is measured; the timer is Python on a general-purpose OS and jitter is unmeasured under ROS; the node writes no hash-chained flight log; `/gate/reset` and UDP 5008 are unauthenticated; the frozen-frame check is not wired in at runtime; one forward corridor, `Twist` only. See the README and `SAFETY_CONCEPT.md` for the full list.

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

The `qerra_msgs` package (`src/qerra_msgs`) is not built by the ROS 2 CI workflow yet.

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

1. **Reaction-time bounding** — The gate's envelope assumes `t_react = 32 ms`,
   which is the Webots lockstep value. On a real robot the reaction time also
   includes the scan period (a Hokuyo URG-04LX is nominally 10 Hz), DDS queues,
   executor delay, and the base controller's acceleration ramps. How do you bound
   this end to end, and is `ros2_tracing` the right tool for it?

2. **Integration topology** — Direct remapping (planner `/cmd_vel` → gate →
   `/cmd_vel_safe` → base) or a `twist_mux` priority chain? ROS 2 does not
   enforce a sole publisher on `/cmd_vel_safe`. How do you keep other publishers
   off the safety topic in practice? Would a worked Nav2 example help?

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
   raw `std_msgs` topics, so the `qerra_msgs` package now exists.

Any input is valuable — even a short comment on one question helps shape
the next small improvements.

---

**Contact:** marunigno@gmail.com (subject: QERRA Robotics Feedback)  
**License:** Apache-2.0

*Early-stage research tool — not certified for production safety systems.*
