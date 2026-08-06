# QERRA-v2 Classical for Robotics Integration

QERRA-v2 Classical is a fully explainable, 100% classical ethical evaluation
engine based on 12 immutable human-centred vectors (SEMEV-12). It is designed
as a **Condition node** in robot Behaviour Trees — an ethical safety layer that
evaluates situations before action execution.

**Key strengths for robotics:**
- Deterministic and auditable (no black boxes)
- Full per-vector reasoning and similarity scores in every response
- Ready ROS 2 bridge (`ros2_bridge.py`) — a non-blocking ROS 2 Action Server
  (`/qerra/evaluate`, type `qerra_msgs/action/QerraEvaluate`)
- Live public API for immediate testing — no installation required

**Repository:** https://github.com/marunigno-ship-it/QERRA-v2-classical  
**Live API:** https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/docs

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

3. **Latency and real-time** — What latency budget is acceptable for an
   ethical condition node in humanoid or mobile manipulation tasks? The live
   API call currently takes 1–3 seconds; an on-device deployment would be
   faster.

4. **Integration patterns** — Would worked examples using Nav2, MoveIt 2, or
   specific Behaviour Tree libraries (PyTrees, BehaviorTree.CPP) be helpful
   for your evaluation?

Any input is valuable — even a short comment on one question helps shape
the next small improvements.

---

**Contact:** marunigno@gmail.com (subject: QERRA Robotics Feedback)  
**License:** AGPL-3.0 (commercial licensing available on request)

*Early-stage research tool — not certified for production safety systems.*
