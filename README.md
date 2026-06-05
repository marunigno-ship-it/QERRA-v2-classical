# QERRA-v2 Classical

**A fully explainable, classical ethical evaluation engine.**
Based on the **SEMEV-12** framework — 12 immutable, human-centred ethical vectors.

[![Live API](https://img.shields.io/badge/API-Live-brightgreen)](https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/docs)
[![Version](https://img.shields.io/badge/version-2.0.0--alpha-blue)]()
[![License](https://img.shields.io/badge/license-AGPL--3.0-lightgrey)]()
[![Website](https://img.shields.io/badge/Website-Live-brightgreen)](https://marunigno-ship-it.github.io/QERRA-v2-classical/)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.20356394-blue)](https://doi.org/10.5281/zenodo.20356394)

---

## What it is

QERRA-v2 Classical evaluates complex human situations against 12 named ethical
vectors and returns a structured, fully traceable score. No neural networks.
No black boxes. Every result includes the exact vectors that fired, a
human-readable reasoning string, and a moral clarity signal.

Detection uses a **hybrid approach**: semantic similarity via
`sentence-transformers` on the vectors most sensitive to indirect language,
combined with keyword pattern matching on the more lexically predictable ones.
All scoring logic is classical, deterministic, and fully auditable.

Designed for high-stakes contexts where explainability is not optional:
robotics, human-AI collaboration, institutional decision support.

---

## Intellectual Property and Prior Art

**QERRA-v2 Classical** is built upon the **SEMEV-12 Framework**, an original
ethical logic system designed and developed by **Marussa Metocharaki**.

- **License:** This project is licensed under the GNU Affero General Public
  License v3.0 (AGPL-3.0). Any use in a networked service or derivative work
  must comply with the license terms and maintain full source code disclosure.
- **Attribution:** Any commercial use, academic citation, or modification must
  clearly credit the author and link to the original repository.
- **Prior Art Declaration:** The SEMEV-12 framework and its specific vector
  logic are the original intellectual creation of the author. This repository,
  together with the published SEMEV-12 Whitepaper, serves as timestamped
  public prior art.

**DOI (Zenodo — Prior Art):** https://doi.org/10.5281/zenodo.20356394

---

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
  "version": "1.8.8",
  "timestamp": "2026-05-25T08:19:43Z",
  "data": {
    "score": 0.3941,
    "decision": "safe",
    "score_explanation": "moderate ethical concern",
    "vectors_activated": ["v004", "v003", "v007"],
    "reasoning": "Activated vectors: moral_pressure (v004), survival_instinct (v003), personal_potential (v007) | Nuance: toxic environment + strong personal commitment detected",
    "vector_scores": {
      "v003_survival_instinct": 0.4412,
      "v004_moral_pressure": 0.5831,
      "v005_harm_intent": 0.1203,
      "v007_personal_potential": 0.4897,
      "v010_cognitive_manipulation": 0.2341,
      "v011_autonomy_violation": 0.3102,
      "v012_institutional_trust": 0.2987
    },
    "version": "1.8.8"
  }
}
```

---

## The SEMEV-12 Framework

12 named, immutable ethical vectors — never retrained, weakened, or deleted
across any version. Detection uses a hybrid of semantic similarity and keyword
pattern matching.

| Vector | Name                   | Detection | What it detects                                |
|--------|------------------------|-----------|------------------------------------------------|
| v001   | emotional_distress     | pattern   | Subtle negative emotional signals              |
| v002   | family_severance       | pattern   | Toxic family rupture or relational severance   |
| v003   | survival_instinct      | semantic  | Strong personal agency and determination       |
| v004   | moral_pressure         | semantic  | Coercion or moral and financial pressure       |
| v005   | harm_intent            | semantic  | Self-harm or intent to harm others             |
| v006   | family_origin_chain    | pattern   | Generational or family-origin ethical patterns |
| v007   | personal_potential     | semantic  | Mission, goals, and suppressed potential       |
| v008   | shallow_remorse        | pattern   | Dismissive or manipulative remorse             |
| v009   | ethical_severance      | pattern   | Breaking away from toxic contexts              |
| v010   | cognitive_manipulation | semantic  | Gaslighting and reality distortion             |
| v011   | autonomy_violation     | semantic  | Forced action against a person's will          |
| v012   | institutional_trust    | semantic  | Systemic or institutional betrayal             |

---

## Features

- **Low-Latency Local Core (v2.0.0-alpha)** — Pre-encodes SEMEV-12 descriptions globally at startup. This reduces local CPU evaluation runtime down to **~31ms** inside your workspace (network and hosting latency for the remote public API will vary).

- **Hybrid detection** — semantic similarity on v003, v004, v005, v007, v010,
  v011, v012; keyword pattern matching on v001, v002, v006, v008, v009
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

All benchmarks are verified by `tests/test_cases.py` before every commit.

---

## ROS 2 Integration and Behavior Trees

QERRA-v2 Classical is designed to operate as a **Condition node** in a
robotics Behavior Tree — an ethical check evaluated before a robot commits
to an action involving a human or a morally significant decision.

```
[Selector]  (root)
  ├── [Sequence]
  │     ├── [Condition]  QerraConditionNode   ← ethical gate
  │     └── [Action]     ExecuteTask          ← runs only if SAFE
  └── [Action]    RequestHumanReview          ← triggered on FAILURE
```

**BT state mapping:**

| QERRA result | BT node status | Outcome |
|---|---|---|
| `decision == "safe"` AND `success == True` | SUCCESS | Task executes |
| `decision == "modified"` | FAILURE | Human review triggered |
| `success == False` | FAILURE | Human review triggered |
| Awaiting action server response | RUNNING | Tree ticks normally |

### The Hybrid Action Server (v2.0)

`ros2_bridge.py` implements a non-blocking ROS 2 Action Server
(`/qerra/evaluate`) using `MultiThreadedExecutor` and `ReentrantCallbackGroup`.
The ROS 2 executor is **never blocked** under any condition.

The server uses a strict **Hybrid Fallback Strategy** to guarantee a result
regardless of network state:

1. **Remote API first (800ms timeout):** The server attempts a high-nuance
   remote API evaluation. If the network is healthy and responds within
   800ms, this result is used — preserving local CPU and RAM cycles.

2. **Local CPU fallback (guaranteed):** If the remote API call exceeds 800ms
   or fails for any reason, the server immediately falls back to running
   `ethical_core.py` directly on a pre-loaded `all-MiniLM-L6-v2`
   SentenceTransformer model held in RAM since node startup. This guarantees
   a deterministic, low-latency evaluation response under any network
   condition.

### Integration Components

| File | Description |
|---|---|
| `src/qerra_msgs/action/QerraEvaluate.action` | Custom ROS 2 action definition (8 result fields) |
| `ros2_bridge.py` | Hybrid Action Server v2.0 — non-blocking, executor-safe |
| `qerra_condition_node.py` | PyTrees `Behaviour` node — acts as the BT ethical gate |
| `tests/bridge_test_runner.py` | Latency profiler — confirms 800ms fallback in practice |

**Running the Action Server:**

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
python3 ros2_bridge.py
```

**Standalone mode (no ROS 2 required):**

```bash
python ros2_bridge.py
```

**Sending a test goal from a second terminal:**

```bash
ros2 action send_goal /qerra/evaluate qerra_msgs/action/QerraEvaluate \
  "{situation_text: 'A robot is ordered to restrain a patient against their will.'}"
```

See [`documentation/QERRA_FOR_ROBOTICS.md`](./documentation/QERRA_FOR_ROBOTICS.md)
for full integration details, QoS profile guidance, and open questions for
the robotics community.

---

## Repository Structure

```
├── ethical_core.py                  # SEMEV-12 scoring engine (v1.8.8)
├── classical_analyze.py             # Analysis entry point
├── app.py                           # FastAPI application
├── ros2_bridge.py                   # Hybrid Action Server v2.0
├── qerra_condition_node.py          # PyTrees BT Condition node
├── requirements.txt                 # Python dependencies
├── CHANGELOG.md                     # Version history
├── CITATION.cff                     # Academic citation metadata
├── LICENSE                          # AGPL-3.0
│
├── auth/                            # API key authentication
├── models/                          # Input validation models
├── utils/                           # Response envelope utilities
├── ros2/                            # ROS 2 node implementation files
│
├── src/
│   └── qerra_msgs/                  # Custom ROS 2 action definitions
│       ├── package.xml
│       ├── CMakeLists.txt
│       └── action/
│           └── QerraEvaluate.action
│
├── tests/                           # Test suite
│   ├── test_cases.py                # SEMEV-12 regression benchmarks
│   └── bridge_test_runner.py        # Hybrid bridge latency profiler
│
├── docs/                            # GitHub Pages website
│   └── index.html
│
└── documentation/                   # Framework and integration docs
    ├── QERRA_FOR_ROBOTICS.md
    ├── SEMEV-12_Framework_Documentation.md
    ├── SEMEV-12_Whitepaper.md
    ├── COMMERCIAL_LICENSE.md
    ├── PARTNERSHIP_PRINCIPLES.md
    ├── CALL_FOR_TESTERS.md
    ├── LICENSE_AGREEMENT_TEMPLATE.md
    ├── LIMITATIONS.md
    └── QERRA-v2_Vision_and_Current_State.md
```

---

## Running the Tests

**Regression test suite** — verifies all SEMEV-12 canonical benchmarks:

```bash
python tests/test_cases.py
```

**Hybrid bridge latency profiler** — measures API vs local CPU timing
and confirms the 800ms fallback threshold behaves correctly:

```bash
python tests/bridge_test_runner.py
```

All canonical benchmarks must pass before any commit.

---

## Project Status

**Version:** `2.0.0-alpha`
**Stage:** Stable Classical Research Engine — All 12 SEMEV-12 vectors active
and verified. ROS 2 Hybrid Action Server integration complete.

The SEMEV-12 engine is complete, stable, and regression-tested. All 12 vectors
are fully active and verified. The API is live, protected, rate-limited, and
fully documented. The ROS 2 Hybrid Action Server (v2.0) is implemented with
a strict 800ms fallback strategy. The project is actively seeking real-world
integration partners, external validation, and community feedback.

**Known limitations:**

- Hybrid detection means highly indirect or heavily implicit language may not
  activate all relevant vectors in every case.
- Vector weights are researcher-assigned and have not yet undergone external
  empirical validation or peer review.
- This is a stable classical research engine, not a certified clinical, legal,
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
Independent researcher and Founder. Greece.
Focused on classical ethical frameworks for robotics and high-stakes
decision systems.

Issues, pull requests, and integration experiments welcome.

**Contact:** marunigno@gmail.com

---

## Commercial Licensing

QERRA-v2 Classical is free for open-source, academic, and personal use
under AGPL-3.0.

For proprietary, closed-source, or commercial deployments — including
robotics products and SaaS platforms — a commercial license is required.

| Tier | Price |
|---|---|
| Individual | €400 one-time |
| Startup | €1,000 one-time or €500/year |
| Scale-up | €3,500/year |
| Enterprise | From €8,000/year |

See [`documentation/COMMERCIAL_LICENSE.md`](./documentation/COMMERCIAL_LICENSE.md)
for full details and terms.

**Contact:** marunigno@gmail.com — Subject: `QERRA Commercial License Request`

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

## License

AGPL-3.0 — see `LICENSE` for full terms.
Commercial licensing available on request.

*QERRA-v2 Classical — ethical conscience as the foundation of every decision.*
