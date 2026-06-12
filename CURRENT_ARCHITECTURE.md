# Current Architecture of QERRA-v2 Classical

**Last updated:** 12 June 2026

## Overview

QERRA-v2 Classical is a fully explainable, classical ethical evaluation engine designed for high-stakes environments, particularly humanoid and collaborative robots. It consists of two tightly integrated but distinct layers:

## SEMEV-12 — Ethical Core Layer

The primary ethical reasoning engine.  
- 12 immutable, human-centered ethical vectors  
- Hybrid detection (semantic + pattern matching)  
- Fully auditable reasoning with vector-level scores and explanations  
- Version: v1.9.0 (all 12 vectors semantic)

## QERRA-HSR v0.1 — Physical Safety Companion Layer

**New companion layer** added for real-world robot deployment (cafes, factories, homes, streets).

**Purpose:** Provide fast, deterministic physical safety decisions that work alongside (and sometimes override) the ethical layer.

**Key Characteristics:**
- Pure Python, zero ML, zero extra dependencies
- Extremely lightweight (< 1ms per evaluation)
- Three vectors: `immediate_physical_distress`, `human_isolation`, `environmental_hazard_proximity`
- Deterministic threshold-based logic with combined conditions
- 12 regression tests (all passing)
- Output states: `CLEAR` / `MONITOR` / `CRITICAL`
- `robot_task_interruptible` flag respected but does not block CRITICAL decisions

**Interaction Rule:** Physical safety (HSR) takes priority when CRITICAL. SEMEV-12 ethical evaluation continues in parallel for MONITOR cases.

**Status:** Completed and integrated as of 12 June 2026.

---

This architecture ensures the robot can be both ethically aware and physically safe in real environments.
