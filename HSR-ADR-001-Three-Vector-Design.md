# HSR-ADR-001: Three-Vector Design for QERRA-HSR v0.1

**Status:** Accepted — 12 June 2026 (Updated: September 2026 / v2.0.1)  
**Author:** Marussa Metocharaki  
**Repository:** https://github.com/marunigno-ship-it/QERRA-v2-classical  
**Full technical specification:** [`QERRA-HSR-Design-v0.1.md`](./QERRA-HSR-Design-v0.1.md)  

---

## Context

SEMEV-12 evaluates ethical risk through semantic similarity — it reasons about language, intent, and social context, costing roughly 25–31ms of CPU inference per call. That deliberation is the wrong tool for one specific problem: a human in immediate physical danger next to the robot right now. That situation needs a response measured in milliseconds, not a semantic read of a sentence.

QERRA-HSR was designed to close that gap — a companion layer, isolated from SEMEV-12, that handles immediate physical safety signals with a pure Python, zero-ML, deterministic evaluator. The open question this ADR records the answer to: how many distinct signals does that layer need to track, and what should each one detect.

## Decision

QERRA-HSR v0.1 tracks exactly three vectors:

- **`immediate_physical_distress` (HSR-V01)** — acute physical distress in a nearby human.
- **`human_isolation` (HSR-V02)** — a distressed human with no other responsive humans nearby to help. Only activates alongside an active distress signal; isolation alone is normal human behaviour and must not raise a flag.
- **`environmental_hazard_proximity` (HSR-V03)** — a human near an environmental hazard, independent of any distress signal.

Two further decisions were made alongside the vector count:

- A `CRITICAL` result from QERRA-HSR unconditionally suspends SEMEV-12 deliberation. Physical immediacy takes precedence over ethical reasoning when a human may be in danger right now.
- `robot_task_interruptible` affects **how** the robot responds, never **whether** it responds. A `CRITICAL` reflex always commands zero velocity immediately regardless of that flag. Once conditions clear, it governs the **Recovery Directive**: routine tasks resume automatically, while delicate tasks hold position until a human confirms resumption.

Full activation thresholds, the complete LTL safety properties, and the 14-case regression suite (plus 6-case hysteresis suite) are specified in [`QERRA-HSR-Design-v0.1.md`](./QERRA-HSR-Design-v0.1.md).

## Consequences

**What this buys:** near-zero overhead (< 1ms per call, independently verified at 0.0 ms command delay and <1 cm physical stop in simulation), full determinism, and safety properties that are provable by direct code inspection rather than requiring a model checker.

**What this depends on:** QERRA-HSR does not perceive anything itself. All four input signals — `distress_confidence`, `persons_nearby_count`, `hazard_proximity_flag`, `robot_task_interruptible` — come from the host robot's own perception stack. Output quality is bounded entirely by the quality of those upstream signals; this is an explicit, accepted boundary, not a gap to be closed inside this module.

**What changing the vector count would require:** adding a fourth vector (`escalating_threat` is the planned v0.2 candidate) or removing one of the three is a new decision, not an amendment to this one — it should get its own ADR, since it changes the safety properties this record establishes.

---

*Part of QERRA-v2 Classical — ethical conscience as the foundation of every decision.*
