# QERRA-v2 Classical for Robotics Integration

QERRA-v2 Classical is an open-source autonomous execution firewall and supervisory guard for robot Behavior Trees, ROS 2 pipelines, and motor actuators.

It enforces a strict separation between high-level deliberation (planners, LLMs, Behavior Trees) and low-level physical actuation:
> *"Values and ethics can screen and rank what a robot wants to do, but only a deterministic gate decides what the wheels do."*

**Key strengths for robotics engineering:**
- **Deterministic Actuator Gate (Layer 1A):** Pure-function integer state machine owning exclusive motor authority. Enforces dynamic stopping envelope $d_{stop}(v) = \lceil v^2 / (2a) \rceil + margin$ ($a=500\text{ mm/s}^2, margin=300\text{ mm}$), 150 ms proposer freshness watchdog, and fail-closed latched recovery with operator reset.
- **Tamper-Evident SHA-256 Flight Recorder:** Appends every discrete control cycle to an offline-verifiable rolling hash chain (`verify_log.py`).
- **Assistive Safety Reflex (Layer 1B / QERRA-HSR):** Pure Python reflex under ISO 13482 for personal care cobots (distress, isolation, proximity) with Property HSR-5 recovery hold contracts.
- **Deterministic Moral Refusal (Layer 2 / SEMEV-12):** Evaluates 12 ethical dimensions on local CPU (~25ms). Coercive commands trigger fail-closed stops and a physical head-shake "No" in simulation.
- **Values Action Selection (Layer 3 / QERRA-THRIVE):** PyTrees Action Ranker selecting courteous motions (whisper transit, lawn avoidance) among already-safe actions.
- **Simulation Validated & 110 CI Tests:** Validated across 7 PAL Robotics TIAGo AMR scenarios in Webots R2025a (Demo 7 baseline: `RUN_1791713619`).
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

See `ros2_bridge.py` for the full implementation.

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

**Running the node (rclpy required):**

```bash
source /opt/ros/humble/setup.bash   # adjust for your ROS 2 distro
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

1. **Action interface design** — Does the current `QerraEvaluate` Action
   (situation text + HSR signals in; score, decision, reasoning, and
   activated vectors out) fit naturally into your decision pipelines or
   Behaviour Trees? Early feedback favoured a dedicated action package
   over raw `std_msgs` topics — the `qerra_msgs` package now exists.

2. **QoS profiles** — What QoS settings (Reliability, Durability, History
   depth) would be appropriate for a safety-critical ethical check in your
   pipeline? The bridge currently uses the ROS 2 default (reliable, depth 10).

3. **Latency and real-time budgets** — The wheel-level Supervisory Gate evaluates within sub-millisecond compute budgets on a 32 ms tick loop with a strict 150 ms proposal freshness limit. High-level moral evaluation (SEMEV-12) takes ~25 ms on CPU, or runs over HTTP with an 800 ms timeout. In Behavior Trees, condition nodes evaluate asynchronously without blocking motor control loops. What latency budgets and watchdog timeouts do you typically enforce between wheel-level kinematic safety gates and high-level learned planners in your own stacks?

4. **Integration patterns** — Would worked examples using Nav2, MoveIt 2, or
   specific Behaviour Tree libraries (PyTrees, BehaviorTree.CPP) be helpful
   for your evaluation?

Any input is valuable — even a short comment on one question helps shape
the next small improvements.

---

**Contact:** marunigno@gmail.com (subject: QERRA Robotics Feedback)  
**License:** AGPL-3.0 (commercial licensing available on request)

*Early-stage research tool — not certified for production safety systems.*
