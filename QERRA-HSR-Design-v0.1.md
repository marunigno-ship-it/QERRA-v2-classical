# QERRA-HSR v0.1 — Proposed Design Document

**Status:** Implemented — 12 June 2026  
**Author:** Marussa Metocharaki  
**Repository:** https://github.com/marunigno-ship-it/QERRA-v2-classical  
**Companion to:** SEMEV-12 v1.9.0

## 1. Purpose and Scope

QERRA-HSR is a deterministic physical safety companion layer for humanoid and collaborative robots. It works alongside SEMEV-12 to handle immediate physical risks while SEMEV-12 focuses on ethical concerns.

## 2. The Three Vectors

- **immediate_physical_distress (HSR-V01)**  
  Detects acute physical distress in nearby humans.

- **human_isolation (HSR-V02)**  
  Detects when a distressed human is isolated (no other responsive humans nearby).

- **environmental_hazard_proximity (HSR-V03)**  
  Detects when a human is near an environmental hazard.

## 3. Input Interface

```python
HSRInput(
    distress_confidence: float,        # 0.0–1.0
    persons_nearby_count: int,
    hazard_proximity_flag: bool,
    robot_task_interruptible: bool
)

4. Output States

CLEAR
MONITOR
CRITICAL

5. Key Design Principles

Pure Python, zero ML, zero extra dependencies
< 1ms overhead (Hugging Face free tier compatible)
Fully deterministic and explainable
Physical safety can override ethical evaluation when CRITICAL

6. Status

Fully implemented, tested with 12 regression cases, pushed to main.



