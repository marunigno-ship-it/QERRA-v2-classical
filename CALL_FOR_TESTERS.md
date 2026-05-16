# QERRA-v2 Classical — Call for Early Testers

QERRA-v2 Classical is an open-source ethical decision framework for AI systems and humanoid robots. It evaluates text inputs across 12 ethical vectors (SEMEV-12) and returns a risk score, decision, and fully traceable human-readable reasoning.

**Version:** 1.8.1-restored  
**Live API (free, no account needed):**  
https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/docs  

**Public demo key (for /analyze):**  
`TEST-2026-QERRA-CLASSICAL-PUBLIC-KEY-98765`

---

## What I am looking for in testers

I am looking for a small number of serious early testers — researchers, engineers, or practitioners working in AI safety, robotics, applied ethics, or human-AI interaction who are willing to spend 30–60 minutes genuinely testing the system.

**Especially useful:**
- Real-world ethical dilemmas from your field (medical, industrial, care robotics, etc.)
- Prompts that combine moral pressure with strong personal commitment
- Cases where you think the score is wrong — and why
- Robotics scenarios involving conflicting human instructions or high-stakes decisions

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
It runs standalone with no ROS 2 installation and becomes a full publisher/subscriber node when `rclpy` is present.

Published topics when running under ROS 2:
- `/qerra/ethical_score` — `Float32`, risk score
- `/qerra/ethical_decision` — `Bool`, True = safe
- `/qerra/semev12_result` — `String`, full JSON assessment

---

## What you get

- Direct access to the researcher (Marussa Metocharaki) for questions and discussion
- Your feedback will directly shape the next version
- Credit in the CHANGELOG and README if you contribute meaningful test results
- Early access to the ROS2 integration layer when it is ready

---

## How to participate

Send an email to **marunigno@gmail.com** with the subject line `QERRA Tester` and a brief description of your background and interest. No formal application — just a short message.

**GitHub:** https://github.com/marunigno-ship-it/QERRA-v2-classical  
**License:** AGPL-3.0

*This project is in active early development. All access is currently free. This is an early-stage research tool, not a certified clinical or production safety system.*
