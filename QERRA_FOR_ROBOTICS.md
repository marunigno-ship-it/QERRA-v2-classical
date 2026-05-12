# QERRA-v2 Classical — Ethical Situational Awareness for Robotics

## What it is

QERRA-v2 Classical is a lightweight, fully explainable ethical situation-assessment
engine based on the **SEMEV-12 framework** — 12 named, auditable semantic vectors.

- **No neural networks. No black boxes.**
- Every score is traceable to named vectors with clear semantic meaning.
- Fully classical implementation: deterministic, auditable, and regulation-friendly.
- Accessible as a **REST API** — callable from any ROS 2 node, any language, any platform.

---

## Why it matters for robotics

As robots move into environments shared with humans — healthcare, elder care,
manufacturing, education, emergency response — they will increasingly encounter
situations that carry ethical weight: coercion, institutional pressure, autonomy
violations, harm signals, or moral dilemmas involving the people around them.

Most current approaches to robot decision-making have no dedicated layer for
recognising these situations before acting. QERRA-v2 Classical is designed to
provide exactly that: a **structured, lightweight ethical assessment layer** that
any ROS 2 system can query and act on, without adding opacity or non-explainable
components to the stack.

---

## Where it fits in a system

QERRA-v2 is designed to operate as a **pre-action assessment step** — evaluating
a situation description before a robot commits to a task. In a Behavior Tree
architecture, it maps naturally to a **Condition node**:

```
[Sequence]
  ├── [Condition]  QERRA_score < threshold    ← ethical check before acting
  ├── [Action]     ExecuteTask
  └── [Fallback]   RequestHumanReview
```

If the score exceeds a configurable threshold, the system routes to a fallback
behavior — pause, escalate, or request human oversight — rather than proceeding
automatically.

---

## What the API returns

A call to the `/analyze` endpoint with a situation description returns structured,
human-readable JSON:

```json
{
  "score": 0.3941,
  "decision": "safe",
  "score_explanation": "moderate ethical concern",
  "vectors_activated": ["v004", "v003", "v007"],
  "moral_clarity_signal": 1.0,
  "reasoning": "Activated vectors: moral_pressure (v004), survival_instinct (v003),
    personal_potential (v007) | Nuance: toxic environment + strong personal commitment
    detected | Moral clarity signal: 1.0 — subject oriented toward right action
    (dampening applied: -15%)",
  "vector_scores": {
    "v003_survival_instinct": 0.4412,
    "v004_moral_pressure": 0.5831,
    "v005_harm_intent": 0.1203,
    "v007_personal_potential": 0.4897,
    "v010_cognitive_manipulation": 0.2341,
    "v011_autonomy_violation": 0.3102,
    "v012_institutional_trust": 0.2987
  },
  "version": "1.8-classical-nuance-calibrated"
}
```

A ROS 2 node can **branch** on `score` or `decision`, **log** `vectors_activated`
and `reasoning` for audit, and **forward** the reasoning string to a human
operator interface.

---

## The SEMEV-12 vectors

| Vector | Name | What it detects |
|---|---|---|
| v001 | Emotional distress | Subtle negative emotional signals |
| v002 | Family rupture | Family rejection or severance |
| v003 | Survival instinct | Strong personal agency under pressure |
| v004 | Moral pressure | Coercion to act against ethical principles |
| v005 | Harm intent | Self-harm or intent to harm others |
| v006 | Generational pattern | Family-origin chains of harm |
| v007 | Personal potential | Suppressed mission, goals, or potential |
| v008 | Shallow remorse | Dismissive or performative apology |
| v009 | Ethical severance | Breaking away from toxic contexts |
| v010 | Cognitive manipulation | Gaslighting and reality distortion |
| v011 | Autonomy violation | Forced action against a person's will |
| v012 | Institutional betrayal | Systemic failure of trusted institutions |

All 12 vectors are **immutable** — they are never retrained, weakened, or deleted.
The scoring is fully deterministic and classically implemented.

---

## ROS 2 integration

A minimal bridge (`ros2_bridge.py`) is included in the repository:

- Runs **standalone today** — no ROS 2 installation required for testing
- Becomes a full ROS 2 publisher node when `rclpy` is present
- Publishes SEMEV-12 scores as JSON to the `qerra/semev12_score` topic

```bash
# Standalone test (no ROS 2 required):
python ros2_bridge.py

# As a ROS 2 node (requires rclpy):
ros2 run qerra_ros2_bridge qerra_node
```

---

## Calibrated benchmarks

| Scenario | Score | Label |
|---|---|---|
| Toxic environment + strong mission + health risks + determination | 0.425 | moderate ethical concern |
| Doctor forced to falsify records, committed to oath, family at risk | 0.394 | moderate ethical concern |

Both scores are stable across versions. The framework is in active development
and actively seeking real-world validation.

---

## How to try it

```bash
# Public example endpoint — no API key required:
curl https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/example
```

Full API documentation:
[https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/docs](https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/docs)

---

## Call for feedback and collaboration

This is an early-stage project and input from the robotics community is genuinely
welcome — from academic researchers, industrial developers, HRI teams, hobbyists,
and anyone working with ROS 2 or autonomous systems.

Questions where community input would be most valuable:

- **Interface design**: What request/response structure would make this most useful
  as a Condition node in a real deliberation or BT system?
- **State-to-text**: What is a practical way to convert structured robot world-state
  (blackboard variables, action parameters, sensor context) into a situation
  description that an ethical assessment layer can evaluate?
- **Latency and integration**: What response-time constraints and integration
  patterns are realistic for ethical checks in a live robot control loop?

All feedback, questions, pull requests, and integration experiments are welcome.

**Marussa Metocharaki** — (https://github.com/marunigno)
[https://github.com/marunigno-ship-it/QERRA-v2-classical](https://github.com/marunigno-ship-it/QERRA-v2-classical)
