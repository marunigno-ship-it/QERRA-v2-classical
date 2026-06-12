# HSR-ADR-001: Three-Vector Design for QERRA Human Safety Response Layer

**Status:** Accepted  
**Date:** 12 June 2026  
**Author:** Marussa Metocharaki

## Context

SEMEV-12 handles ethical reasoning. For real-world robot deployment we needed a fast, deterministic physical safety layer that can act immediately and sometimes override ethical evaluation.

## Decision

We created **QERRA-HSR v0.1** with exactly **three vectors**:

1. **immediate_physical_distress** (HSR-V01)  
2. **human_isolation** (HSR-V02)  
3. **environmental_hazard_proximity** (HSR-V03)

## Rationale

- Three vectors keep the layer lightweight and explainable.
- Covers the most critical physical risks in collaborative environments.
- Designed to work in parallel with SEMEV-12 (physical safety takes priority when CRITICAL).

## Key Design Rules

- Pure Python, zero ML, <1ms overhead
- Deterministic threshold logic
- Combined condition: moderate distress + isolation = CRITICAL
- robot_task_interruptible affects *how* the robot responds, never *whether*

## Status

Fully implemented, 12 regression tests passing, integrated into the repository as of 12 June 2026.

---

This is a permanent record for the HSR layer.
