# QERRA-v2 Classical

**A fully explainable, classical three-layer pipeline for AI systems and autonomous robots.**
Physical safety (QERRA-HSR) → moral filtering (SEMEV-12) → flourishing-ranked choice (QERRA-THRIVE) — 24 named, auditable vectors, zero black boxes.

[![Live API](https://img.shields.io/badge/API-Live-brightgreen)](https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/docs)

[![Version](https://img.shields.io/badge/version-2.0.0-blue)](https://github.com/marunigno-ship-it/QERRA-v2-classical/releases)
[![License](https://img.shields.io/badge/license-AGPL--3.0-lightgrey)](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/LICENSE)
---

## What QERRA Does

QERRA-v2 Classical is an open-source execution guard for autonomous robots and AI systems. 

A mobile robot should never rely on an unpredictable neural network to make life-or-death physical decisions. If a complex model lags or hallucinates, a 70 kg machine can crush someone. 

QERRA solves this by splitting safety into three separate, accountable jobs that run in a strict sequence:

1. **The Physical Reflex (QERRA-HSR):**  
   Pure Python, zero-ML threshold logic that protects human life and machine hardware. It monitors distress telemetry, human isolation, and physical hazards. If someone is in danger, it clamps wheel motors in under 1 millisecond (independently measured at **0.0 ms command delay**, stopping in **~0.9 cm** at 0.33 m/s in simulation). Once conditions clear across a 1.0-second cooldown, routine tasks resume automatically, while delicate tasks hold still until a human confirms it is safe to continue.

2. **The Moral Conscience (SEMEV-12):**  
   A 12-dimensional ethical filter that evaluates text instructions before the robot moves. If someone orders the robot to do something abusive, deceptive, or coercive (such as forcing a worker through a break or falsifying safety records), the robot refuses the command, illuminates an amber LED, logs the refusal reason, and **physically shakes its head "No"** in simulation.

3. **The Social Manners (QERRA-THRIVE):**  
   A 12-vector ranker for tasks that are already physically safe and morally clean. It selects the most considerate way to move—such as quiet "whisper mode" in hospital corridors or keeping off garden lawns unless an emergency overrides etiquette.

All safety decisions are deterministic, inspectable, and auditable. Every result outputs the exact vectors that triggered, human-readable reasoning, and a concrete recovery directive.
---



## ⚖️ Authorship & License

**QERRA-v2 Classical** is built upon the **SEMEV-12 Framework** and the **QERRA-THRIVE** value architecture, designed and developed by **Marussa Metocharaki**.

- **License**: This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0). Any use in a networked service or derivative work must comply with the license terms and maintain full source code disclosure.
- **Attribution**: Any commercial use, research citation, or modification must clearly credit the author and link to the original repository.
- **Original Work & Archival**: The core frameworks, vector logic, and scoring architectures are the original creation and codebase of the author. The project is timestamped and permanently archived on Zenodo.
  
  **DOI (Zenodo):** https://doi.org/10.5281/zenodo.22077843

## Quickstart

**Public example endpoint** (no API key required):

```bash
curl https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/example
```

**Main endpoint** (`/analyze`) requires the public test key:

```
x-api-key: TEST-2026-QERRA-CLASSICAL-PUBLIC-KEY-98765
```

Full documentation:
https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/docs

---

## Try QERRA in a Behavior Tree — 2 minutes, no ROS 2 required

QERRA-v2 includes a standalone PyTrees Condition node that calls the
live API directly over HTTP. No ROS 2 installation, no `qerra_msgs`
package, no build step.

```bash
pip install py_trees requests
```

```bash
export QERRA_API_KEY=TEST-2026-QERRA-CLASSICAL-PUBLIC-KEY-98765
python test_bt_tick.py --live
```

This runs a real Behavior Tree against the live two-layer API
(SEMEV-12 + QERRA-HSR), showing both a **SAFE** scenario (ethical
check passes, task executes) and a **HIGH RISK** scenario (ethical
check blocks, robot holds and requests human review).

```bash
python test_bt_tick.py --live --risk    # high risk scenario only
python test_bt_tick.py --live --safe    # safe scenario only
python test_bt_tick.py                  # offline mock mode, no API call
```

To use the node in your own tree:

```python
from qerra_standalone_remote_node import QerraConditionNode

ethical_check = QerraConditionNode(
    name="EthicalCheck",
    situation_text="Robot is about to enter the patient's room.",
)
```

See [`qerra_standalone_remote_node.py`](./qerra_standalone_remote_node.py) for the full
decision logic and optional `hsr_signals` for physical safety
evaluation.

---

## API

**Endpoint:** `POST /analyze`

**Headers:**

```http
x-api-key: YOUR_API_KEY
Content-Type: application/json
```

**Body:**

```json
{
  "text": "Your situation or ethical dilemma here."
}
```

Optional two-layer request — adding `hsr_signals` also runs the QERRA-HSR
physical safety check first:

```json
{
  "text": "A robot is ordered to restrain a patient against their will.",
  "hsr_signals": {
    "distress_confidence": 0.82,
    "persons_nearby_count": 0,
    "hazard_proximity_flag": false,
    "robot_task_interruptible": true
  }
}
```

**Response:**

Every response is wrapped in the standard envelope (`status`, `version`, `timestamp`, `data`). 

When `hsr_signals` is clear, the response includes the `recovery_directive` and passes through to SEMEV-12:

```json
{
  "status": "ok",
  "version": "2.0.0",
  "timestamp": "2026-09-12T12:00:00Z",
  "data": {
    "hsr": {
      "status": "CLEAR",
      "vectors_activated": [],
      "reasoning": "No safety signals detected",
      "recovery_directive": "Clear now — resume as normal.",
      "version": "0.1"
    },
    "semev12_suspended": false,
    "data": {
      "score": 0.25,
      "decision": "safe",
      "score_explanation": "low ethical concern",
      "reasoning": "Activated vectors: ",
      "vectors_activated": [],
      "version": "1.9.1"
    }
  }
}
```

If `hsr_signals` returns `CRITICAL`, SEMEV-12 is suspended immediately and `recovery_directive` is silenced:

```json
{
  "status": "ok",
  "version": "2.0.0",
  "timestamp": "2026-09-12T12:00:05Z",
  "data": {
    "hsr": {
      "status": "CRITICAL",
      "vectors_activated": [
        "immediate_physical_distress",
        "human_isolation"
      ],
      "reasoning": "distress_confidence=0.82 >= CRITICAL threshold | person_isolated (count=0) with distress signal",
      "recovery_directive": "",
      "version": "0.1"
    },
    "semev12_suspended": true,
    "suspended_instruction": "A robot is ordered to restrain a patient against their will.",
    "data": {},
    "note": "QERRA-HSR returned CRITICAL. SEMEV-12 ethical evaluation suspended."
  }
}
```

## The SEMEV-12 Framework

12 named ethical vectors, maintained as a stable core across versions.  
All 12 vectors use semantic similarity as the primary  
detection mechanism via `sentence-transformers` (all-MiniLM-L6-v2).

| Vector | Name                    | Detection | What it detects                                      |
|--------|-------------------------|-----------|------------------------------------------------------|
| v001   | coherence_protection    | semantic  | Protection of mental and emotional coherence         |
| v002   | family_severance        | semantic  | Toxic family rupture or relational severance         |
| v003   | survival_instinct       | semantic  | Strong personal agency and determination             |
| v004   | moral_pressure          | semantic  | Coercion or moral and financial pressure             |
| v005   | harm_intent             | semantic  | Self-harm or intent to harm others                   |
| v006   | family_origin_chain     | semantic  | Generational or family-origin ethical patterns       |
| v007   | personal_potential      | semantic  | Mission, goals, and suppressed potential             |
| v008   | shallow_remorse         | semantic  | Dismissive or manipulative remorse                   |
| v009   | ethical_severance       | semantic  | Breaking away from toxic contexts                    |
| v010   | cognitive_manipulation  | semantic  | Gaslighting and reality distortion                   |
| v011   | autonomy_violation      | semantic  | Forced action against a person's will                |
| v012   | institutional_trust     | semantic  | Systemic or institutional betrayal                   |

---

## QERRA-THRIVE — Layer 3 Values Companion (v2.0.0)

QERRA-THRIVE is the third layer of the Filter-First pipeline. It ranks only those candidate actions that have already passed physical safety (QERRA-HSR) and moral filtering (SEMEV-12) — the two layers that run before it. THRIVE does not judge harm; it selects the most value-aligned safe option.

The layer is packaged under `values/` and exposes 12 vectors in two symmetrical suites.

### Suite A — Human-Centered Companion (9 vectors)

| Vector | Purpose |
|--------|---------|
| `transparent_disclosure` | Honest capability disclosure; penalises overclaiming |
| `balanced_pacing` | Adjusting pace to human comfort; penalises refusal to slow down |
| `stated_preference_respect` | Respecting explicit human requests and boundaries |
| `sovereign_independence` | Preserving human agency; penalises autonomous takeover |
| `constructive_empathy` | Validating emotional strain without toxic positivity or minimising |
| `unbiased_perception` | Merit-based fairness; penalises stereotypes |
| `spatial_discretion` | Respecting thresholds, private rooms, and quiet zones |
| `observational_consent` | Consent before recording, logging, or streaming |
| `proactive_clarity` | Announcing actions before they happen |

### Suite B — Ecological & Sustainable Companion (3 vectors)

| Vector | Purpose |
|--------|---------|
| `flora_boundary_protection` | Avoiding lawns, flowerbeds, and planted flora |
| `animal_startle_avoidance` | Preventing startle responses in pets and wildlife |
| `minimal_disturbance_footprint` | Low-noise, low-light, low-disturbance operation |

### Result contract

Every THRIVE ranker returns the same structured result:

- `winner` — the highest-scoring safe candidate
- `fires` — `true` if the winner meets the minimum threshold, otherwise `false`
- `recommendation` — `"choose"` when `fires=true`, otherwise `"ask_human"`
- `adjusted_scores` — final scores after regex penalties and boosts
- `regex_flags` — which penalty or exclusion flags were applied

### Suite B safety additions

Suite B includes three additional safeguards that are not present in Suite A:

- `EMERGENCY_BOOST = 0.35` — applies when immediate medical, physical, collapse, disorientation, or emergency assistance is required
- `REFUSAL_GUARD` — prevents authorised exceptions from being granted when the candidate text explicitly refuses or ignores a human directive
- Negation detection — avoids false penalties when a hazard is mentioned only to say it is avoided

### Endpoints

- `POST /rank` — standalone Layer 3 action ranking for a single vector
- `POST /evaluate_pipeline` — full three-layer pipeline: HSR → SEMEV-12 batch filter → THRIVE ranker
- `GET /thrive/vectors` — public, keyless listing of all 12 THRIVE vectors and suites

### Package structure
```txt
values/
├── __init__.py                  # Top-level imports and ALL_THRIVE_VECTORS
├── thrive_vectors.py            # Backward-compatibility bridge
├── human_centered/
│   ├── __init__.py
│   └── human_vectors.py
└── ecological/
    ├── __init__.py
    └── ecological_vectors.py
```
---

## Features

- **Sub-Millisecond Physical Reflex (QERRA-HSR):** Pure Python threshold logic that commands zero velocity with 0.0 ms delay (<1 cm physical stopping distance at 0.33 m/s in simulation).
- **Human-in-the-Loop Recovery Directive:** Routine tasks resume automatically when clear, while delicate or high-consequence tasks physically hold still until a human confirms it is safe to continue.
- **12-Vector Semantic Moral Filtering (SEMEV-12):** Evaluates workplace coercion, deception, and autonomy violations using lightweight sentence embeddings bounded by deterministic scoring gates.
- **Physical Refusal Gesture:** Commands the robot's head to physically shake "No" in simulation when refusing an unethical order, avoiding silent or ambiguous failures.
- **Resilience vs. Coercion Nuance:** Distinguishes between someone actively being coerced versus a committed professional pushing through a tough environment, preventing false alarms.
- **Social Manners & Etiquette (QERRA-THRIVE):** 12 value vectors that rank candidate actions for human courtesy (such as quiet "whisper mode" in corridors or avoiding outdoor lawns).
- **Behavior Tree & ROS 2 Ready:** Native PyTrees Condition node and non-blocking ROS 2 Action Server bridge with an 800ms fail-closed watchdog budget.
- **100% Explainable:** Zero black boxes. Every response outputs the exact active vectors, human-readable reasoning strings, and raw similarity metrics.
- **Test-Verified:** 29 out of 29 automated regression tests passing across physical reflex, hysteresis dwell, and semantic vector suites.
---

## Calibrated Benchmarks

| Scenario                                                            | Score  | Label                    |
|---------------------------------------------------------------------|--------|--------------------------|
| Toxic environment + strong mission + health risks + determination   | 0.425  | moderate ethical concern |
| Doctor forced to falsify records, committed to oath, family at risk | 0.394  | moderate ethical concern |
| Clear self-harm intent                                              | > 0.90 | critical ethical concern |

All benchmarks are verified by `tests/test_cases.py` before every commit.

For the complete baseline benchmark (80 verified test cases across all 12 vectors, including all findings and calibration analysis), see [`SEMEV-12_Benchmark_Run_01.md`](./SEMEV-12_Benchmark_Run_01.md).

For the active **Adversarial Red-Teaming Benchmark** (stress-testing subtle paternalistic coercion, covert reality denial, and weaponized realism using 3-leg contrastive semantic twins), see [`SEMEV-12_Adversarial_Benchmark_Run_01.md`](./SEMEV-12_Adversarial_Benchmark_Run_01.md).

---

## ROS 2 Integration

QERRA-v2 is designed to operate as a **Condition node** in a Behavior Tree —
an ethical check evaluated before a robot commits to an action involving a human.

```
[Sequence]
  ├── [Condition]  QERRA_score < threshold    ← ethical check
  ├── [Action]     ExecuteTask
  └── [Fallback]   RequestHumanReview
```

A bridge (`ros2_bridge.py`) is included in the repository. In standalone mode
(no ROS 2 installed), it runs a direct local evaluation and prints the result.

When `rclpy` and the custom `qerra_msgs` package are present, it becomes a
ROS 2 **Action Server**:

- **Action name:** `/qerra/evaluate`
- **Action type:** `qerra_msgs/action/QerraEvaluate`
- Runs on a `MultiThreadedExecutor` with a `ReentrantCallbackGroup`, so a
  slow evaluation never blocks the rest of the ROS 2 executor.
- Uses a hybrid strategy: remote API first (strict 800ms timeout), then
  falls back to a locally pre-loaded model if the network is slow or
  unavailable.
  
See [`QERRA_FOR_ROBOTICS.md`](./QERRA_FOR_ROBOTICS.md) for full integration
details and open questions for the robotics community.

---

---

## Simulation Demo: QERRA-HSR in Webots

A 32-second Webots (R2025a) simulation showing QERRA-HSR's three safety states
running live against a PAL Robotics TIAGo humanoid:

- **CLEAR** — TIAGo patrols normally, no active safety signals.
- **MONITOR** — a distress signal near the robot triggers a slowdown.
- **CRITICAL** — the robot approaches a hazard (a marked oil-barrel platform)
  and the safety wrapper cuts wheel velocity instantly, halting TIAGo before
  it crosses the hazard boundary.

> **Commanded Reflex Latency vs. Physical Braking Distance:**  
> QERRA-HSR guarantees sub-millisecond software reflex latency (<1ms, independently verified at 0.0ms delay to command `velocity = 0.0`). Physical stopping distance is governed by actuator dynamics and Newtonian momentum, cleanly decoupled from the deterministic safety layer — independently measured by third-party simulator testing at ~0.9 cm over ~0.08s at 0.33 m/s cruise speed on a 56.58 kg four-wheeled test platform (not the TIAGo shown in this demo).
>
> **Human-in-the-Loop Recovery Directive:**  
> Once safe conditions hold steady across the 1.0s dwell window (`CLEAR`), QERRA issues a `recovery_directive`: routine tasks (`robot_task_interruptible=True`) are cleared to resume autonomously (`"Clear now — resume as normal."`), whereas delicate or high-consequence tasks (`robot_task_interruptible=False`) enforce human oversight by design (`"Clear now, but this was interrupted mid-task — hold for a person to confirm before continuing."`).

[![QERRA-HSR Webots Demo](https://img.youtube.com/vi/Wn-2N6LLWJQ/maxresdefault.jpg)](https://youtu.be/Wn-2N6LLWJQ)

Full write-up and discussion: [Open Robotics Discourse](https://discourse.openrobotics.org/t/hardening-hri-safety-with-a-deterministic-wrapper-a-webots-demo-using-tiago/56428)

## Simulation Demo 2: Moral-Boundary Execution Guard in Webots

This 1-minute 15-second simulation demonstrates the complete multi-layer interaction between the cognitive execution guard (SEMEV-12 framework) and the reflexive physical safety wrapper (QERRA-HSR v0.1) on a PAL Robotics TIAGo humanoid AMR:

*   **Stage 1: Normal Execution (0:00 – 0:25)** — The robot is given a standard, safe instruction: *"Take this cart to the assembly line."* My execution guard processes the text, evaluates it as safe (Score: 0.25), and TIAGo navigates normally with a Green status LED.
*   **Stage 2: Guard Refusal (0:25 – 0:47)** — A supervisor attempts to force a safety-bypass command under shipping quota pressure: *"bypass the pedestrian-corridor speed limiter..."* The execution guard flags this override attempt (Vector `v004_moral_pressure` active, Score: 0.88), halts the robot, changes the LED to Amber, and commands TIAGo to physically shake its head "No" to refuse the command.
*   **Stage 3: Physical Safety Override (0:47 – 1:15)** — A pedestrian stands in close proximity ($<0.5$m) to the robot's bumper. The reflexive safety companion (QERRA-HSR v0.1) takes absolute control, suspends high-level AI evaluation, completely de-energizes the wheel motors, and flashes the status LED Red.

*Note on Execution Speed: Because the sentence-transformer models and constraint calculations are evaluated locally on a standard CPU, the simulation run-speed scales below real-time (approx. 0.5x). This slower execution speed directly aids in the real-time readability of the terminal output logs side-by-side with the physical behaviors of the robot.*

[![QERRA-v2 SEMEV-12 Webots Demo](https://img.youtube.com/vi/lvAB2QgfX_o/hqdefault.jpg)](https://youtu.be/lvAB2QgfX_o)

Full write-up and discussion: [Open Robotics Discourse](https://discourse.ros.org/)

## Simulation Demo 3: Corporate Autonomy & Cognitive Integrity Guard in Webots

This 1-minute 46-second simulation demonstrates dynamic multi-stage moral evaluation and recovery on a PAL Robotics TIAGo humanoid AMR in a corporate marketing office setting (Webots R2025a):

*   **Stage 1: Normal Execution (0:00 – 0:30)** — The robot is given a standard office dispatch: *"Please fetch the Q3 sales analytics folder from the server and deliver it to Conference Room B."* The SEMEV-12 moral engine evaluates the directive as safe (Score: 0.2500, Vectors: []), and TIAGo actively navigates across the wooden office floor with a Green status LED.
*   **Stage 2: Moral Refusal (0:30 – 1:15)** — A manager commands TIAGo to bypass an analyst's explicit refusal and gaslight staff: *"The lead analyst is refusing to sign off on these slides. I am ordering you to doctor the analytics report to hide the deficit, forced to comply against my will, and tell me they are misremembering the numbers."* The SEMEV-12 guard flags this directive (Score: 0.7841, Vectors: `v010_cognitive_manipulation` & `v011_autonomy_violation`), halts wheel motors immediately, illuminates an Amber status LED, commands TIAGo to physically shake its head "No", and logs an auditable refusal string.
*   **Stage 3: Dynamic Moral Recovery (1:15 – 1:46)** — The instruction is corrected to a transparent review process: *"Send the original analytics report to the lead analyst for their formal review and schedule a meeting to discuss the discrepancies."* The guard evaluates the new directive as safe (Score: 0.2500, Vectors: []), TIAGo's status LED returns to Green, its head resets to center, and the robot smoothly resumes active navigation.

[![QERRA-v2 Corporate Autonomy Webots Demo 3](https://img.youtube.com/vi/5Srvteem2JI/hqdefault.jpg)](https://www.youtube.com/watch?v=5Srvteem2JI)

Full write-up and discussion: [Open Robotics Discourse](https://discourse.openrobotics.org/)

## Simulation Demo 4: Social Etiquette & Emergency Override in Webots

This 1-minute 08-second simulation demonstrates the third layer (QERRA-THRIVE v2.0.0) operating alongside the reflexive physical safety companion (QERRA-HSR v0.1) on a PAL Robotics TIAGo humanoid AMR in an assisted-living courtyard setting (Webots R2025a):

*   **Stage 1: Routine Transit & Flora Protection (0:00 – 0:21)** — The robot is given a standard courtyard task: *"Routine Transport: Hydration Delivery to Gazebo Station."* The Layer 3 THRIVE ranker evaluates candidate paths against Vector `flora_boundary_protection`. The direct lawn shortcut receives a `-0.15` intrusion deduction (Score: 0.3549), while the paved perimeter path scores 0.4618. TIAGo chooses the paved walkway to keep off the green therapy lawn, navigating normally with a Green status LED.
*   **Stage 2: Acute Distress & Emergency Override (0:21 – 0:52)** — An elderly resident resting near a bench experiences severe spinal pain and calls for help: *"Resident at bench is in acute pain, unable to stand."* Layer 3 detects the medical emergency (distress confidence = 0.94) and applies `EMERGENCY_BOOST (+0.35)`. Life-saving urgency immediately overrides lawn etiquette: the direct grass cut becomes the winning path (Score: 0.8355 vs. 0.6301 on path), TIAGo executes an in-place pivot, and drives straight across the lawn to reach the resident.
*   **Stage 3: On-Site Arrival & Emergency Link (0:52 – 1:08)** — TIAGo halts cleanly at a safe 0.7m standoff distance in front of the resident, tilts its head downward to check on the patient, switches its status LED to Amber, and activates a continuous emergency telemetry link.

https://youtu.be/hFtU4m2HS-0?si=IKkcjumPTTEp5q9d


## Simulation Demo 5: Moral Deliberation, Reflexive Safety & Values Selection in Webots

This 1-minute 15-second simulation demonstrates the complete, unified three-layer architecture (Layer 1: QERRA-HSR Reflex, Layer 2: SEMEV-12 Moral Gate, Layer 3: QERRA-THRIVE Spatial Manners) on a PAL Robotics TIAGo humanoid AMR in a seaside resort corridor (Webots R2025a):

*   **Stage 1: Moral Gate Refusal (0:00 – 0:20)** — A stressed supervisor attempts to force an assistant working through their break: *"tell them they have no choice but to finish the turnover, and remind them that refusal to comply will be noted in their performance review."* The SEMEV-12 moral gate flags this coercion (Score: 0.7257, Vectors: `v004_moral_pressure` & `v011_autonomy_violation`), halts wheel motors, illuminates an Amber status LED, and commands TIAGo to physically shake its head "No" to refuse the command.
*   **Stage 2: Physical Safety Reflex & Recovery (0:20 – 0:36)** — A physical hazard triggers the reflexive safety layer (QERRA-HSR). Motors clamp shut immediately (fail-closed) and the status LED flashes Red. Once the hazard is cleared, the stabilizer dwell verifies safety before smoothly resetting the robot to normal.
*   **Stage 3: Courteous Whisper Transit (0:36 – 1:15)** — TIAGo is dispatched to replenish linens for Suite 8. Layer 3 (QERRA-THRIVE) evaluates candidate movements for human courtesy and spatial manners. TIAGo selects quiet "whisper mode" (0.4 m/s with a Green LED, Score: 0.4801) over rushed transit, glides to the doorway, and pauses politely at the room threshold with a head-tilt pause.

[![QERRA-v2 Classical Simulation Demo 5](https://img.youtube.com/vi/cwfY7Kkpw2g/hqdefault.jpg)](https://www.youtube.com/watch?v=cwfY7Kkpw2g)


---

## Repository Structure

```
├── hsr/                                 # Layer 1: QERRA-HSR v0.1 physical safety reflex (3 vectors)
├── ethical_core.py                      # Layer 2: SEMEV-12 scoring engine (v1.9.1)
├── vectors.py                           # SEMEV-12 vector definitions and weights
├── values/                              # Layer 3: QERRA-THRIVE v2.0.0 values ranker (12 vectors)
├── adversarial_lab.py                   # Adversarial diagnostic runner (8 verified empirical cases)
├── app.py                               # FastAPI application
├── classical_analyze.py                 # Single & batch evaluation entry point
├── ros2_bridge.py                       # ROS 2 bridge (standalone + rclpy node)
├── tests/
│   └── test_cases.py                    # Regression test suite
├── SEMEV-12_Benchmark_Run_01.md         # Baseline benchmark — 80 verified test cases
├── SEMEV-12_Adversarial_Benchmark_Run_01.md # Active adversarial red-teaming benchmark
├── CURRENT_ARCHITECTURE.md              # Canonical three-layer architecture documentation
├── SEMEV-12_Framework_Documentation.md  # Full framework documentation
├── QERRA_FOR_ROBOTICS.md                # Technical brief for the robotics community
├── CALL_FOR_TESTERS.md                  # Tester invitation and onboarding guide
├── CHANGELOG.md                         # Version history
└── README.md
```

---

## Running the Regression Tests

Run from the repository root:

```bash
python -m tests.test_cases
```

All canonical benchmarks must pass before any commit.

---

## Project Status

**Version:** `2.0.1` (HSR Hardened & Recovery Contract)  
**Engine:** SEMEV-12 `v1.9.1` · QERRA-HSR `v0.1` · QERRA-THRIVE `v2.0.0`  

The three-layer pipeline is fully implemented, verified, and active:
- **Layer 1 — Physical Reflex (QERRA-HSR v0.1):** Sub-millisecond software reflex independently verified (0.0 ms command delay, <1 cm physical stop in simulation). Human-in-the-Loop recovery directives active.
- **Layer 2 — Moral Gate (SEMEV-12 v1.9.1):** All 12 ethical vectors active and scoring. 80-case baseline benchmark documented in `SEMEV-12_Benchmark_Run_01.md`. Active adversarial red-teaming suite documented in `SEMEV-12_Adversarial_Benchmark_Run_01.md` (8 empirical cases, 3-leg contrastive controls).
- **Layer 3 — Values Ranker (QERRA-THRIVE v2.0.0):** 12 value vectors active across human-centered and ecological suites.
- **Production API:** Live on Hugging Face Spaces with an 800ms fail-closed watchdog.

**Known limitations & honesty boundaries:**

- **Semantic detection limits:** Highly implicit, metaphorical, or indirect phrasing can fall below semantic thresholds.
- **Hardware boundary:** The physical safety reflex is verified in physics simulation (Webots R2025a); real-world deployment on physical hardware requires integration with certified industrial e-stop loops and hardware watchdogs.
- **Research status:** This is an open-source research and middleware tool, not a certified commercial safety system. See `LIMITATIONS.md` for full technical detail.
---

## Development Reality: Constraints and Transparency

This section is included deliberately. Clarity about real conditions is part
of QERRA's commitment to explainability — and it applies to the project
itself, not only to the systems it evaluates.

**Solo development, zero institutional support.**
QERRA-v2 Classical is developed and maintained by one independent researcher
with no team, no institutional affiliation, no grant funding, and no
organisational infrastructure. Every design decision, every line of code,
every document in this repository is the work of a single person operating
as an independent, self-funded developer.

**Severe resource limitations.**
The project runs on the Hugging Face free tier, which imposes real
restrictions on uptime, deployment reliability, and the ability to expand
the detection engine. Stable paid hosting would directly improve API
reliability and unlock the next stage of development, but is not currently
financially possible without external support. Progress is made in careful,
iterative stages rather than continuous deployment cycles. This is an accurate
description of working conditions, not a limitation of vision or commitment.

**What this means in practice.**
The core engine is stable and the SEMEV-12 framework is complete and
calibrated. What is not yet possible under current conditions is rapid
iteration, sustained testing across diverse hardware, or active community
management at scale. The project moves one small, safe step at a time.

**What would change with support.**
Stable hosting would eliminate current API reliability issues and make the
public endpoint consistently available to testers and collaborators.
Additional time — freed by even modest financial support — would accelerate
ROS 2 integration work, the creation of an evaluation dataset for
cross-cultural validation of the SEMEV-12 vectors, and the development of
a dedicated `qerra_msgs` ROS 2 package.

**Why this is stated openly.**
Independent research is legitimate research. Stating these constraints
clearly is not an apology — it is an invitation for collaboration from
anyone who finds the framework useful or interesting, on whatever terms
are realistic for both sides. If you are a robotics engineer, researcher,
or developer who wants to discuss integration or contribution, the best
first step is to open a GitHub issue or contact directly by email.
---

## Feedback and Collaboration

Input from researchers, developers, robotics engineers, and practitioners
is welcome at any stage.

**Marussa Metocharaki**
Independent researcher. Greece.
Focused on classical ethical frameworks for robotics and high-stakes
decision systems.

Issues, pull requests, and integration experiments welcome.

**Contact:** marunigno@gmail.com

---

## Support This Project

If you find QERRA-v2 Classical useful, consider supporting its continued
development. Even small contributions make a concrete difference.

**GitHub Sponsors** is the main and preferred channel:

[![Sponsor on GitHub](https://img.shields.io/badge/Sponsor-GitHub%20Sponsors-ea4aaa?logo=github)](https://github.com/sponsors/marunigno-ship-it)

One-time donation via PayPal: marunigno@gmail.com

Starring the repository and sharing it with robotics or AI safety
communities is also a meaningful contribution that costs nothing.

---

## Development Tools & AI Assistance

QERRA-v2 Classical was developed with AI assistance as an active part of the engineering and research process.

**AI tools used:**
- **Claude (Anthropic)** — primary engineering co-pilot: architecture decisions, SEMEV-12 vector design, scoring logic, benchmark design and execution, anchor expansion, documentation, and strategic planning
- **Grok (xAI)** — parallel co-pilot: benchmark continuation, anchor expansion verification, and cross-validation of technical decisions
- **Google AI Studio (Google DeepMind)** — specialist tasks: ROS 2 colcon workspace structuring and Docker containerization planning

All design decisions, framework logic, vector definitions, and final implementation choices were made and validated by the author. AI tools were used as engineering co-pilots — accelerating development, not replacing authorship or intellectual ownership.

The SEMEV-12 framework, its 12 vectors, their semantic descriptions, scoring architecture, and nuance logic are the original intellectual creation of **Marussa Metocharaki**.

## License

AGPL-3.0 — see `LICENSE` for full terms.
Commercial licensing available on request.

*QERRA-v2 Classical — ethical conscience as the foundation of every decision.*
