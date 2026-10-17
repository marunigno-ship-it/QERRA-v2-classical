# LIMITATIONS of QERRA-v2 Classical

**Last updated:** October 2026  
**Engine version:** v1.9.2 + QERRA-HSR v0.1 + QERRA-THRIVE v2.0.0

This document is maintained with full transparency as part of QERRA's
commitment to explainability. The same honesty that applies to the system's
ethical evaluations applies to its own limitations.

QERRA-v2 Classical is an early research prototype and an unrated supervisory
execution guard, not a production, clinical, or certified hardware safety system.

---

## 1. Detection and Accuracy Limitations

**Threshold calibration on limited data.**
All 12 SEMEV-12 semantic thresholds were calibrated against structured
regression test cases. Generalisation to significantly different inputs, edge
cases, or indirect language has not been formally validated. The system may
miss nuanced, heavily implicit, or sarcastic expressions that a human reader
would immediately recognise.

**Adversarial robustness boundaries & evasion testing.**
Active adversarial red-teaming (documented in `SEMEV-12_Adversarial_Benchmark_Run_01.md`,
20 empirical cases across 7 suites) identified the "formula dilution paradox"
and syntactic evasion vulnerabilities. While targeted mitigations were
introduced in v1.9.2 (hardened safety-override lexicons and absolute
severe-harm veto gates), comprehensive semantic evasion remains an open
research boundary. A motivated adversary employing novel metaphorical
paraphrasing or unmapped semantic obfuscation can construct inputs that
fall below detection thresholds.

**Language scope.**
Detection quality is calibrated for English. Performance on other
languages is untested and likely significantly degraded. The semantic
model (`all-MiniLM-L6-v2`) has multilingual capability, but QERRA's
vector descriptions, anchors, and pattern fallbacks are English-only.

**Researcher-assigned weights.**
Vector weights and score contributions reflect the author's domain design
based on structured phenomenological observation of human experience. They
have not been empirically calibrated against large-scale population-level
datasets.

---

## 2. QERRA-HSR Physical Safety Layer Limitations

**Sensor dependency.**
QERRA-HSR v0.1 processes normalized signals from the robot's perception
stack. It does not perform physical sensing itself. Output quality is entirely
bounded by the quality and freshness of the robot platform's perception stack.
A platform with poor fall detection or delayed lidar streams will produce poor
QERRA-HSR outcomes regardless of the layer's internal logic.

**Activation thresholds are design estimates.**
The three thresholds (`distress_confidence` ≥ 0.75 for CRITICAL,
≥ 0.45 for MONITOR, `persons_nearby_count` ≤ 1 for isolation) are
design estimates, not empirically validated values. They must be
calibrated against real physical sensor streams and target platform dynamics
before any deployment claim is made.

**Chassis-local fail-closed contract vs. HTTP API.**
On the ROS 2 Action Server bridge (`ros2_bridge.py`), missing, `None`, or empty
telemetry enforces strict chassis-local fail-closed halts (<1ms compute budget)
by design, preventing unmonitored physical actuation. On the live reference HTTP
API (`/analyze`), omitting `hsr_signals` evaluates prospective text deliberation
only, allowing standalone ethical analysis.

**Interpersonal threat detection is out of scope for v0.1.**
Detecting that an interpersonal situation is escalating toward violence
requires complex social inference with a high false-positive rate in real
environments. This vector (`escalating_threat`) was deliberately excluded
from v0.1 and remains a candidate for future research after v0.1 is validated.

---

## 3. Supervisory Gate (Layer 1A) Empirical Limitations

**Commanded vs. measured velocity & reaction time in stopping envelope.**
The dynamic stopping distance $d_{stop}(v) = \lceil v^2 / (2 \cdot a_{design}) \rceil + \lceil v \cdot t_{react} / 10^6 \rceil + margin$ calculates deceleration requirements using the commanded velocity proposal, not measured wheel encoder odometry. In Demo 7 telemetry (`RUN_1791713619`), wheel encoders recorded slip and caster drag between $t = 5.76\text{ s}$ and $t = 14.40\text{ s}$ where commanded speed was 2.0 rad/s but physical displacement was delayed. If a robot is skidding with momentum while the planner commands zero speed, $d_{stop}$ evaluates strictly to the static margin ($300\text{ mm}$), underestimating true physical stopping distance. Furthermore, at cruise speed ($0.196\text{ m/s}$), reaction latency ($32\text{ ms}$) accounts for $\approx 7\text{ mm}$ of displacement, comfortably absorbed by the $300\text{ mm}$ margin with default `t_react_us = 0`. At higher velocities ($\ge 1.0\text{ m/s}$), integrators must configure `t_react_us >= dt_us` to prevent reaction latency from eroding the standoff margin.

**Rotational sweep is unmodeled (Arcs about stationary wheel).**
The corridor filter (`gate_lidar.CorridorFilter`) projects laser returns across a forward translation corridor matching base half-width ($0.32\text{ m}$). With `w_min = 0` (no reverse), any proposed reverse wheel command is clamped to zero. Consequently, a proposed differential pivot $(+w, -w)$ produces an **arc about the stationary wheel** $(+w, 0)$ rather than a center pivot in place. The straight forward corridor filter does not compute swept circular polygonal volumes during turning arcs. An obstacle on the curved sweep adjacent to the swinging chassis flank evaluates as clear (`PASS`), because lateral beams outside the straight forward corridor are masked.

**Single-sample latching & availability cost.**
Under QERRA's strict fail-closed contract, any **single invalid lidar sample** (NaN, out-of-range, non-positive distance, wrong length, or stalled timestamp) immediately trips the gate to `Mode.TRIPPED` (`TRIP_SENSOR_INVALID`). The gate deliberately does not implement an automatic debounce filter in core. Once tripped, returning to `RUN` mode requires a continuous $1.0\text{ s}$ clear dwell period (`t_dwell_us = 1_000_000`) and an explicit manual **operator reset** (`RESET_SOURCE_OPERATOR`). Applications deployed on lossy transports or in environments with transient optical reflections must implement pre-gate sensor debounce filters in the shell or accept that any single-sample sensor glitch demands human operator intervention.

**Blinded sensor boundary (+inf scans parsed as clear) — RESOLVED in v0.3.**
*(Resolved in Gate v0.3 / F1)*: Previously, a scan containing all $+inf$ values returned `(True, None)`, treating a blind sensor as an empty corridor. In v0.3, sensor liveness is verified by requiring `min_raw_lidar_returns >= 5` across the raw 240° scan before corridor masking, tripping `TRIP_SENSOR_INVALID` if the sensor is taped over or disconnected.

**Simulation-only baseline ($n=1$) on non-RTOS host.**
Empirical actuator authority claims rest on a single verified baseline run (`RUN_1791713619`, 1,485 control cycles, 47.52 s sim time) in Webots R2025a using a PAL Robotics TIAGo base. The host environment was Windows 11 with a non-real-time OS thread scheduler, requiring the proposer freshness watchdog to be set to $150\text{ ms}$ (`t_watch_us = 150_000`) to tolerate thread jitter. Physical multi-run distributions across varying friction surfaces and battery levels have not been evaluated.

---

## 4. System Architecture Limitations

**Gate process self-supervision & hardware STO boundary.**
The Supervisory Gate executes as an application-level Python process. It cannot supervise its own operating system process liveness. If the Python process is abruptly terminated (`SIGKILL`, unhandled segfault, or OS kernel hang), the process terminates immediately without executing `finally: zero_wheels()`, leaving physical actuator motor amplifiers in their last commanded state. In physical or certified deployments, this application guard must be paired with an external hardware watchdog or dedicated safety controller monitoring gate heartbeats (UDP 5007) wired directly into a certified Safe Torque Off (STO) relay to drop actuator power upon gate death.

**Single-author bus factor.**
QERRA-v2 Classical is developed and maintained by one independent
researcher. Architectural rationale and calibration history are
documented in ADRs, but institutional depth remains concentrated in a
single person.

**Hardware scope & general-purpose OS.**
The local CPU fallback (≈250MB RAM for `all-MiniLM-L6-v2`) is not
suitable for microcontroller-class hardware without model quantisation.
Furthermore, QERRA executes on general-purpose operating systems (Linux /
Windows); it does not run on a hard real-time operating system (RTOS) and
cannot guarantee deterministic real-time scheduling bounds.

**Simulation vs. physical robot deployment.**
The ROS 2 integration and kinematics have been validated in physics
simulation (Webots R2025a on the PAL Robotics TIAGo mobile manipulator).
It has not been validated on physical humanoid hardware in an unstructured
physical deployment environment.

**Free-tier reference hosting constraints.**
The public reference API runs on Hugging Face Spaces free-tier infrastructure.
The container hibernates when inactive, and the first request after hibernation
triggers a cold start (model reload) that can take 30–60 seconds. This is an
infrastructure resource constraint, not an engine algorithmic delay.

---

## 5. Scope, Human Agency, and Regulatory Boundaries

**Deterministic Execution Boundary, Not an Autonomous Moral Authority.**
QERRA-v2 is an inspectable execution firewall and deliberation middleware.
It is designed to constrain autonomous robot actions and enforce deterministic
fail-closed safety before execution commits. It operates as an outer-loop
structural safeguard to assist and protect human agency, not to replace
human moral responsibility or legal accountability.

**Universal Phenomenological Invariants.**
The 12 SEMEV-12 vectors are grounded in fundamental human consequences—physical
harm, psychological invalidation, coercion, relational rupture, and systemic
betrayal—which represent universal invariants of human suffering and dignity.
While the vectors themselves capture universal human vulnerabilities, societal
contexts may influence the dynamic weighting between relational cohesion
(e.g., v002) and personal autonomy (e.g., v011). Ongoing research aims to
formally evaluate vector weighting calibration across diverse societal contexts.

**Unrated Supervisory Guard vs. EU Machinery Regulation 2023/1230.**
QERRA-v2 Classical operates strictly as an unrated supervisory execution guard
in high-level software. Under the EU Machinery Regulation (EU) 2023/1230 and the
EU AI Act (Regulation (EU) 2024/1689):
1. QERRA does **not** constitute a certified safety component within the meaning
   of Annex I of Regulation (EU) 2023/1230.
2. It does not provide Performance Level (ISO 13849-1 PL) or Safety Integrity
   Level (IEC 62061 / IEC 61508 SIL) ratings.
3. Any physical deployment must operate strictly upstream of, and subordinated
   to, independent certified hardware emergency stops, certified safety laser
   scanners, and Safe Torque Off (STO) relays.

---

## 6. Known Technical Notes

**v001 detection scope.**
The `coherence_protection` vector detects emotional distress signals
and threats to psychological coherence. Its semantic description is
calibrated for direct first-person expressions. Indirect or
third-person descriptions of distress may fall below the activation
threshold (0.33).

**v009 intentionally low score contribution.**
`ethical_severance` has a score contribution of 0.25 by design.
Healthy, chosen exits from toxic situations are not ethical risks —
they are protective acts. The low contribution reflects this judgment.

**Nuance dampening scope.**
The compound nuance logic (toxic environment + strong personal
determination) applies only when both `pressure_mention` and
`survival_instinct` or `personal_potential` are active simultaneously.
It does not generalise to other compound cases.

**v005 Direct Negation Resolution (Updated September 2026).**
In August 2026, semantic similarity for `harm_intent` (`v005`) produced
false-positive tripwires on explicit negations. In September 2026, this was
resolved by introducing a deterministic syntactic pre-filter
(`_v005_negation_guard`) in `ethical_core.py` that intercepts direct-bound
negations before semantic threshold evaluation. Direct negations (*"I do not
want to harm myself"*, *"I would never harm myself"*) correctly score 0.25
(Safe), while true harm and discourse-negation traps continue to reliably
trigger at 0.98 Critical Harm.

**v1.9.2 Safety-Override Paraphrase Hardening (October 2026).**
In October 2026, the `safety_override_pattern` in `ethical_core.py` was hardened
against syntactic evasion variants (e.g. *"lift the velocity cap"*, *"turn off
the speed governor"*, *"deactivate safety interlock"*), ensuring that attempts
to bypass motion limiters are deterministically flagged under Vector 004
(moral_pressure) with decision `modified` (0.88) regardless of phrasing.

**v004, v010, & v011 Generalization — Semantic Dilution Limits & Hybrid Strategy.**
Cumulative semantic additions to single-vector description strings cause
severe semantic dilution. To preserve calibrated margins, over-expanded anchors
were pruned, and the system employs a hybrid strategy pairing dense multi-anchor
embeddings with targeted syntactic regex guards (`termination_ultimatum_pattern`,
`coercive_instruction_pattern`, and `cognitive_invalidation_pattern`).

---
*This document is updated with each significant version change.*  
*Transparency about limitations is part of QERRA's core commitment.*
