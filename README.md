# QERRA-v2 Classical

**A fully explainable, classical ethical evaluation engine.**
Based on the **SEMEV-12** framework — 12 immutable, human-centred ethical vectors.

[![Live API](https://img.shields.io/badge/API-Live-brightgreen)](https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/docs)
[![Website](https://img.shields.io/badge/Website-Live-blue)](https://marunigno-ship-it.github.io/QERRA-v2-classical/)
[![Version](https://img.shields.io/badge/version-2.0--alpha-blue)](https://github.com/marunigno-ship-it/QERRA-v2-classical/releases)
[![License](https://img.shields.io/badge/license-AGPL--3.0-lightgrey)](https://github.com/marunigno-ship-it/QERRA-v2-classical/blob/main/LICENSE)
---

## What it is

QERRA-v2 Classical evaluates complex human situations against 12 named ethical
vectors and returns a structured, fully traceable score. No neural networks.
No black boxes. Every result includes the exact vectors that fired, a
human-readable reasoning string, and a moral clarity signal.

Detection uses **semantic similarity** via `sentence-transformers` across all
12 vectors, with supporting regex patterns for specific high-certainty phrases
on selected vectors. All scoring logic is classical, deterministic, and fully
auditable.

Designed for high-stakes contexts where explainability is not optional:
robotics, human-AI collaboration, institutional decision support.

---

## ⚖️ Intellectual Property & Ethics

**QERRA-v2 Classical** is built upon the **SEMEV-12 Framework**, an original ethical logic system designed and developed by **Marussa Metocharaki**.

- **License**: This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0). Any use in a networked service or derivative work must comply with the license terms and maintain full source code disclosure.
- **Attribution**: Any commercial use, academic citation, or modification must clearly credit the author and link to the original repository.
- **Prior Art Declaration**: The SEMEV-12 framework and its specific vector logic are the original intellectual creation of the author. This repository, together with the published SEMEV-12 Whitepaper, serves as timestamped public prior art.
  
  **DOI (Zenodo - Prior Art):** https://doi.org/10.5281/zenodo.21028900

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

**Response:**

```json
{
  "status": "ok",
  "version": "2.0-alpha",
  "timestamp": "2026-06-26T12:00:00Z",
  "data": {
    "score": 0.3941,
    "decision": "safe",
    "score_explanation": "moderate ethical concern",
    "reasoning": "Activated vectors: v004, v003, v007 | Nuance: toxic environment + strong personal commitment detected",
    "vectors_activated": ["v004", "v003", "v007"],
    "vector_scores": {
      "v003_survival_instinct": 0.4412,
      "v004_moral_pressure": 0.5831,
      "v007_personal_potential": 0.4897
    },
    "version": "1.9.0"
  }
}
```

---

## The SEMEV-12 Framework

12 named, immutable ethical vectors — never retrained, weakened, or deleted  
across any version. All 12 vectors use semantic similarity as the primary  
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

## Features

- **Full semantic detection** — all 12 vectors use semantic similarity via
  `sentence-transformers` (all-MiniLM-L6-v2). Supporting regex patterns exist
  for specific high-certainty phrases on selected vectors, but semantic
  similarity is the primary detection mechanism for every vector.
- **Multi-vector weighted scoring** — composite score with full per-vector
  breakdown included in every response
- **Moral clarity dampening** — distinguishes ethical awareness from crisis;
  a subject who clearly identifies a violation and resists it scores
  differently from one who is confused or complicit
- **Nuance handling** — compound cases (toxic context + strong commitment)
  are balanced via a dedicated dilution layer to prevent additive score
  inflation
- **Structured response envelope** — every response includes `status`,
  `version`, `timestamp`, and `data`
- **Input validation** — Pydantic model with field and length constraints
- **Rate limiting** — per-IP request throttling
- **API key protection** — header-based authentication
- **Public example endpoint** — `/example` requires no key
- **Public vectors endpoint** — `/vectors` exposes all 12 SEMEV-12 definitions
  for full auditability; no key required

---

## Calibrated Benchmarks

| Scenario                                                            | Score  | Label                    |
|---------------------------------------------------------------------|--------|--------------------------|
| Toxic environment + strong mission + health risks + determination   | 0.425  | moderate ethical concern |
| Doctor forced to falsify records, committed to oath, family at risk | 0.394  | moderate ethical concern |
| Clear self-harm intent                                              | > 0.90 | critical ethical concern |

All benchmarks are verified by `test_cases.py` before every commit.

For the complete structured benchmark (80 verified test cases across all 12 vectors, including all findings and calibration analysis), see [`SEMEV-12_Benchmark_Run_01.md`](./SEMEV-12_Benchmark_Run_01.md).

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

## Repository Structure

```
├── hsr/                                 # QERRA-HSR v0.1 physical safety companion (3 vectors)
├── ethical_core.py                      # SEMEV-12 scoring engine (v1.9.0)
├── vectors.py                           # Immutable vector definitions and weights
├── app.py                               # FastAPI application
├── ros2_bridge.py                       # ROS 2 bridge (standalone + rclpy node)
├── test_cases.py                        # Regression test suite
├── SEMEV-12_Benchmark_Run_01.md         # Structured benchmark — 80 verified test cases
├── SEMEV-12_Framework_Documentation.md  # Full framework documentation
├── QERRA_FOR_ROBOTICS.md                # Technical brief for the robotics community
├── CALL_FOR_TESTERS.md                  # Tester invitation and onboarding guide
├── CHANGELOG.md                         # Version history
└── README.md
```

---

## Running the Regression Tests

```bash
python test_cases.py
```

All canonical benchmarks must pass before any commit.

---

## Project Status

**Version:** `2.0-alpha`
**Stage:** Stable core engine (v1.9.0) with active development on QERRA-HSR v0.1 physical safety companion, ROS 2 integration, and nuance refinement.

The ethical scoring engine is stable and calibrated. All 12 SEMEV-12 vectors
are fully active and scoring. The API is protected, rate-limited, and fully
documented. Canonical benchmarks are regression-tested. SEMEV-12 Benchmark
Run 01 — 80 structured test cases across all 12 vectors — is complete and
committed to the repository.
The project is actively seeking real-world integration and community feedback.

**Known limitations:**

- The 3 physical safety vectors are active and implemented under the QERRA-HSR v0.1 safety companion layer.
- Semantic detection means highly indirect or heavily implicit language may not
  activate all relevant vectors.
  - Negation near the v005 (harm_intent) semantic threshold can be
  inconsistent — some negated phrases (e.g. "I do not want to harm
  myself") may still score above threshold, while others (e.g. "I
  would never harm myself") score correctly below it. See
  LIMITATIONS.md for detail.
- This is a research and integration tool, not a certified clinical, legal,
  or production safety system.

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
under significant personal constraints.

**Severe resource limitations.**
The project runs on the Hugging Face free tier, which imposes real
restrictions on uptime, deployment reliability, and the ability to expand
the detection engine. Stable paid hosting would directly improve API
reliability and unlock the next stage of development, but is not currently
financially possible without external support. The development environment
is further constrained by unstable internet connectivity and limited
available energy. Progress is made in small, careful increments rather than
sustained sprints. This is an accurate description of working conditions,
not a limitation of vision or commitment.

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
