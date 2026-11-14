# LIMITATIONS of QERRA-v2 Classical

**Last updated:** November 2026  
**Engine version:** Gate Core v0.4 + QERRA-HSR v0.3.1 + ROS 2 Node v0.3.1 (Package metadata v2.4.1)

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
QERRA-HSR v0.3.1 processes normalized signals from the robot's perception
stack. It does not perform physical sensing itself. Output quality is entirely
bounded by the quality and freshness of the robot platform's perception stack.
A platform with poor fall detection or delayed lidar streams will produce poor
QERRA-HSR outcomes regardless of the layer's internal logic.

**Activation thresholds are design estimates.**
The three thresholds (`distress_permille` ≥ 750 for CRITICAL,
≥ 450 for MONITOR, `persons_nearby_count` ≤ 1 for isolation) are
integer permille design estimates, not empirically validated values. They must be
calibrated against real physical sensor streams and target platform dynamics
before any deployment claim is made.

**Perception stream monitor sequence-only scope (Gap 4.4).**
The Layer 1B perception stream monitor (`step_hsr_stream`) validates frame
continuity by checking monotonic `obs_id` sequence counters and timestamps. It
detects sequence freezes (identical counter) and regressions (counter drops).
However, it cannot detect an optically frozen sensor if an upstream producer
node continues running and regenerating fresh sequence counters and timestamps.
Furthermore, in synthetic testing, producer timestamps reflect echoed gate
clock time rather than optical sensor exposure intervals.

**Reflex enforcement coupling (`hsr_required`).**
The stream monitor trips fail-closed (emitting `None` status) during rebase
dwells and sticky freezes. However, `gate_core.py` acts upon this only when
`hsr_required=True` (tripping `TRIP_HSR_INVALID`). If `hsr_required=False` is
configured, corrupt or frozen reflex telemetry emits `(None, None)`, which is
silently ignored by the Gate Core, allowing the robot to continue operating
solely on lidar.

**Chassis-local fail-closed contract vs. HTTP API.**
On the ROS 2 Action Server bridge (`ros2_bridge.py`), missing, `None`, or empty
telemetry enforces strict chassis-local fail-closed halts (<1ms compute budget)
by design, preventing unmonitored physical actuation. On the live reference HTTP
API (`/analyze`), omitting `hsr_signals` evaluates prospective text deliberation
only, allowing standalone ethical analysis.

**Interpersonal threat detection is out of scope for v0.3.**
Detecting that an interpersonal situation is escalating toward violence
requires complex social inference with a high false-positive rate in real
environments. This vector (`escalating_threat`) was deliberately excluded
from the reflex layer and remains a candidate for future research.

---

## 3. Supervisory Gate (Layer 1A) Empirical Limitations

**Commanded vs. measured velocity & reaction time in stopping envelope.**
The dynamic stopping distance $d_{\text{stop}}(v) = \lceil v^2 / (2 \cdot a_{\text{design}}) \rceil + \lceil v \cdot t_{\text{react}} / 10^6 \rceil + margin$ calculates deceleration requirements using the commanded velocity proposal, not measured wheel encoder odometry. In Demo 7 telemetry (`RUN_1791713619`), wheel encoders recorded slip and caster drag between $t = 5.76\text{ s}$ and $t = 14.40\text{ s}$ where commanded speed was 2.0 rad/s but physical displacement was delayed. If a robot is skidding with momentum while the planner commands zero speed, $d_{\text{stop}}$ evaluates strictly to the static margin ($300\text{ mm}$), underestimating true physical stopping distance. In live deployment, `t_react_us` is configured to $32\,000\ \mu\text{s}$ ($32\text{ ms}$, 1 tick) in the Webots simulation controller, expanding the stop envelope at cruise speed ($0.196\text{ m/s}$) from $339\text{ mm}$ to $346\text{ mm}$ ($+7\text{ mm}$, or $347\text{ mm}$ at $200\text{ mm/s}$). In the ROS 2 simulation profile, `t_react_us` is parameterized to $96\,000\ \mu\text{s}$ ($96\text{ ms}$, stopping envelope $358\text{ mm}$ at $196\text{ mm/s}$ or $360\text{ mm}$ at $200\text{ mm/s}$). In the 10 Hz Hokuyo hardware profile, `t_react_us` is $160\,000\ \mu\text{s}$ ($160\text{ ms}$, stopping envelope $371\text{ mm}$ at $196\text{ mm/s}$ or $372\text{ mm}$ at $200\text{ mm/s}$). At higher velocities ($\ge 1.0\text{ m/s}$), integrators must configure `t_react_us >= dt_us` to prevent reaction latency from eroding the standoff margin. The 96 ms and 160 ms budgets are engineering cycle estimates, not physically measured latency distributions.

**Rotational sweep is unmodeled & AR-2 symmetrical reverse clamping.**
The corridor filter (`gate_lidar.CorridorFilter`) projects laser returns across a straight forward translation corridor matching base half-width ($0.32\text{ m}$). Under the AR-2 Option A policy (`w_min = 0`), because the robot lacks rearward sensor coverage, any proposal commanding reverse rotation on either wheel causes **both wheel outputs to clamp symmetrically to zero** `(0, 0)`. Consequently, differential center pivots $(+w, -w)$ and reverse maneuvers are completely halted fail-closed rather than executed. For permitted forward-only turning maneuvers where both wheels rotate forward ($w_L > 0, w_R > 0, w_L \ne w_R$), the robot moves along a curved arc ($R = v/\omega$). The straight forward corridor filter does not compute swept circular polygonal volumes along these curved turning trajectories; lateral obstacles adjacent to the swinging chassis flank outside the straight forward corridor evaluate as clear (`PASS`).

**Single-sample latching & availability cost.**
Under QERRA's strict fail-closed contract, any **single invalid lidar sample** (NaN, out-of-range, non-positive distance, wrong length, or stalled timestamp) immediately trips the gate to `Mode.TRIPPED` (`TRIP_SENSOR_INVALID`). The gate deliberately does not implement an automatic debounce filter in core. Once tripped, returning to `RUN` mode requires a continuous $1.0\text{ s}$ clear dwell period (`t_dwell_us = 1_000_000`) and an explicit manual **operator reset** (`RESET_SOURCE_OPERATOR`). Applications deployed on lossy transports or in environments with transient optical reflections must implement pre-gate sensor debounce filters in the shell or accept that any single-sample sensor glitch demands human operator intervention.

**Blinded sensor boundary (+inf scans parsed as clear) — RESOLVED in v0.3.**
*(Resolved in Gate v0.3 / F1)*: Previously, a scan containing all $+inf$ values returned `(True, None)`, treating a blind sensor as an empty corridor. In v0.3, sensor liveness is verified by requiring `min_raw_lidar_returns >= 5` across the raw 240° scan before corridor masking, tripping `TRIP_SENSOR_INVALID` if the sensor is taped over or disconnected.

**LiDAR freshness watchdog relies on simulated fault injection (V5).**
In simulation, `LidarPipeline.process()` stamps scan freshness using the current simulation timestamp unless the caller passes `stalled=True`. The Webots controller sets `stalled=True` only when the fault injection switch `QERRA_LIDAR_FAULT` is configured (`freeze` or `stale`) and simulation time exceeds `QERRA_LIDAR_FAULT_SIM_S`. The stale watchdog ($T_{\text{stale}} = 96\text{ ms}$) therefore exercises software timeout recovery under simulated fault injection; it does **not** track real hardware sensor acquisition intervals, hardware bus packet timestamps, or serial driver latencies.

**Global raw returns vs. forward-arc occlusion boundary (V6).**
The raw return liveness threshold (`min_raw_lidar_returns >= 5`) counts finite laser returns across the entire 240° Hokuyo scan (667 or 682 beams). In a corridor or room, reflections off lateral walls satisfy this threshold even if the forward-facing center arc is completely obscured, taped over, or blinded. While an obstacle directly ahead in the forward corridor will trigger `TRIP_OBSTACLE` when detected, a dead forward sensor arc with live side walls will not trigger `TRIP_SENSOR_INVALID`.

**Proposer session arbitration & restart lockout boundaries (F3 / V4).**
The process restart arbitration mechanism introduced in Gate v0.3 / F3 uses a `session_id` in proposal datagrams to allow a newly spawned proposer (`seq = 0`) to supersede a terminated proposer that left high sequence numbers (`seq = 500+`) in the socket buffer. This mechanism has four documented boundaries:
1. *Wall-clock non-monotonicity:* In `scripts/untrusted_proposer.py`, `session_id = int(time.time() * 1000)` relies on POSIX wall-clock time. If the host system clock steps backward (NTP step adjustment, VM snapshot rollback, container migration, or manual clock correction), a restarted proposer receives a lower `session_id` than the previous process, recreating the restart lockout if stale packets remain in the OS buffer. Furthermore, sub-millisecond restarts risk identical `session_id` collisions.
2. *Unbounded integer DoS:* In `gate/gate_ipc.py`, any non-negative integer is accepted without an upper bound. A rogue process on localhost can broadcast datagrams with `session_id = 2**63 - 1`, preempting legitimate proposals within the 256-packet drain window.
3. *Stateless drain scope:* `drain_proposals()` reinitializes `newest_proposal = None` on every tick; arbitration is strictly local to the datagrams queued in the OS socket buffer at that control cycle. It does not track cross-tick session history.
4. *Trust boundary mismatch:* The deliberation proposer is explicitly an untrusted actor (AR-2, C-1). In a safety-critical architecture, arbitration cannot depend on untrusted clients self-assigning unforgeable, monotonically increasing epoch tokens.

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
simulation (Webots R2025a on the PAL Robotics TIAGo mobile manipulator) and
in a Linux ROS 2 Jazzy container. It has not been validated on physical
humanoid or mobile manipulator hardware in an unstructured physical environment.

**Free-tier reference hosting constraints.**
The public reference API runs on Hugging Face Spaces free-tier infrastructure.
The container hibernates when inactive, and the first request after hibernation
triggers a cold start (model reload) that can take 30–60 seconds. This is an
infrastructure resource constraint, not an engine algorithmic delay.

---

## 5. Adversarial & Security Boundaries (Verified in Test Suite)

**Localhost is an assumed trusted process boundary (Section 4.6).**
Localhost UDP ports (5005, 5006, 5007, 5008) and ROS 2 topics are unauthenticated and unencrypted. QERRA does not defend against hostile local processes running under the same OS user. Two concrete vulnerabilities have been proven through executable unit tests (`tests/test_adversarial_hsr.py`):
1. **Masked-distress re-arm exploit (Section 4.6a):** If a legitimate perception producer is silenced after a real distress stop, an unauthenticated local attacker can transmit a counter regression (`obs_id = 0`), supply 5 clean ticks spaced to reach $\ge 160\text{ ms}$ elapsed dwell, maintain `CLEAR` for the 1.0 s Gate dwell, and issue an operator reset string (`"operator"`). The Gate returns to `Mode.RUN` despite genuine distress having occurred. (Verified in `test_adversarial_masked_distress_rearm_succeeds_without_auth`).
2. **Ingestion buffer crowding exploit (Section 4.6b):** Ingestion from UDP sockets is bounded by `MAX_DRAIN_PER_CALL = 256` datagrams per tick. If an attacker floods $\ge 260$ valid `CLEAR` datagrams into the socket queue, a trailing legitimate `CRITICAL` datagram is left unread in the OS buffer, delaying the protective stop across control cycles. (Verified in `test_adversarial_flood_above_max_drain_delays_critical`).
3. **Actuator authority non-claim in ROS 2:** The ROS 2 DDS transport does not enforce sole-publisher authority. Any local node publishing to `/cmd_vel_safe` bypasses the supervisory gate entirely. SROS2 permissions and OS-level containerization are required to enforce write authority.

---

## 6. ROS 2 Node Architecture Limitations

**Twist interface lacks planner generation timestamp.**
`QerraGateNode` subscribes to standard `geometry_msgs/msg/Twist` on `/cmd_vel`. Because `Twist` carries no header stamp, the node assigns `sim_stamp_us = now_us` upon message receipt. Consequently, the proposal watchdog ($150\text{ ms}$) measures transport and subscription callback delay at the Gate, but cannot detect compute lag or stalled cycles inside the upstream planner before publication.

**No zero command on node termination.**
In `QerraGateNode.destroy_node()`, network sockets and flight logger file descriptors are cleanly closed, but no final zero-velocity command is published to `/cmd_vel_safe`. Actuator safety upon node death depends entirely on downstream base controller command watchdogs.

**Synchronous disk `fsync` inside the 32 ms tick (Requirement R-10).**
When `flight_log_path` is enabled, `GateLogger.append()` executes synchronous `os.fsync()` inside `_tick_callback()`. On spinning disks, saturated SSDs, or virtualized storage, an `fsync` blocking longer than 32 ms delays subsequent control cycles without raising an error.

**Permanent process latching (`NodeFaultLatch`).**
Any unhandled tick exception latches `NodeFaultLatch` permanently for the lifetime of the process, continuously holding 0.0 m/s wheel output. The latch cannot be cleared by `/gate/reset`. Automatic node respawning in launch configurations must be disabled, as process restarts erase in-memory latch states.

**LaserScan metadata validation.**
In `_scan_callback()`, length integrity is strictly enforced (`len(ranges) == lidar_n_expected`), but scan geometry metadata (`angle_min`, `angle_increment`, `frame_id`) is not validated.

---

## 7. Scope, Human Agency, and Regulatory Boundaries

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

## 8. Known Technical Notes

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
