# QERRA-v2 Classical — Call for Early Testers

QERRA-v2 Classical is an open-source ethical decision framework for AI systems
and humanoid robots. It evaluates text inputs across 12 ethical vectors (SEMEV-12)
and returns a risk score, decision, and fully traceable human-readable reasoning.

**Version:** 1.8.1-restored  
**Live API (free, no account needed):**  
https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/docs

**Public demo key (for /analyze):**  
`TEST-2026-QERRA-CLASSICAL-PUBLIC-KEY-98765`

---

## What I am looking for in testers

I am looking for a small number of serious early testers — researchers, engineers, or
practitioners working in AI safety, robotics, applied ethics, or human-AI interaction
who are willing to spend 30–60 minutes genuinely testing the system.

**Especially useful:**
- Real-world ethical dilemmas from your field (medical, industrial, care robotics, etc.)
- Prompts that combine moral pressure with strong personal commitment
- Cases where you think the score or decision is wrong — and why
- Robotics scenarios involving conflicting human instructions or boundary cases

---

## What the API returns

Every response includes:
- `score` — float 0.0 to 1.0 (0.0 = no concern, 1.0 = critical)
- `decision` — `"safe"` or `"modified"`
- `score_explanation` — plain-language label
- `reasoning` — which vectors fired and why
- `vectors_activated` — list of SEMEV-12 vector IDs
- `vector_scores` — per-vector semantic similarity scores

---

## ROS 2 integration

A ROS 2 bridge (`ros2_bridge.py`) is included in the repository.  
It runs standalone with no ROS 2 installation and becomes a full
publisher/subscriber node when `rclpy` is present.

Published topics when running under ROS 2:
- `/qerra/ethical_score` — `Float32`, risk score
- `/qerra/ethical_decision` — `Bool`, True = safe
- `/qerra/semev12_result` — `String`, full JSON assessment

---

## What you get

- Direct access to the researcher for questions and discussion
- Your feedback will directly shape the next version
- Credit in CHANGELOG and README for meaningful test contributions
- Early access to the ROS 2 integration layer as it develops

---

## How to participate

Email **marunigno@gmail.com** with subject line `QERRA Tester` and a brief
description of your background and interest. No formal application needed.

**GitHub:** https://github.com/marunigno-ship-it/QERRA-v2-classical  
**License:** AGPL-3.0

*All access is currently free. This is an early-stage research tool,
not a certified clinical or production safety system.*

---

## How to contribute

After testing, the most helpful things you can do are:
- Open a GitHub Issue with your test scenario, the result you got, and your observations — even a short comment is useful
- Or email your feedback directly to marunigno@gmail.com

There is no required format. One test case and a few honest sentences about what you found is enough. Every piece of real-world feedback directly shapes the next version of the SEMEV-12 engine.

---

*QERRA-v2 Classical — ethical conscience as the foundation of every decision.*
