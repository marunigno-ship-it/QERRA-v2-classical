# QERRA-v2 Classical

**A fully explainable, classical ethical evaluation engine.**
Based on the **SEMEV-12** framework — 12 immutable, human-centred ethical vectors.

[![Live API](https://img.shields.io/badge/API-Live-brightgreen)](https://qerra-v2-api-classical-qerra-v2-api-classical.hf.space/docs)
[![Version](https://img.shields.io/badge/version-1.8.1--restored-blue)]()
[![License](https://img.shields.io/badge/license-AGPL--3.0-lightgrey)]()

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
  "version": "1.8.1-restored",
  "timestamp": "2026-05-12T08:00:00Z",
  "data": {
    "score": 0.3941,
    "decision": "safe",
    "score_explanation": "moderate ethical concern",
    "vectors_activated": ["v004", "v003", "v007"],
    "moral_clarity_signal": 1.0,
    "reasoning": "Activated vectors: moral_pressure (v004), survival_instinct (v003), personal_potential (v007) | Nuance: toxic environment + strong personal commitment detected | Moral clarity signal: 1.0 — dampening applied: -15%",
    "vector_scores": {
      "v003_survival_instinct": 0.4412,
      "v004_moral_pressure": 0.5831,
      "v005_harm_intent": 0.1203,
      "v007_personal_potential": 0.4897,
      "v010_cognitive_manipulation": 0.2341,
      "v011_autonomy_violation": 0.3102,
      "v012_institutional_trust": 0.2987
    },
    "version": "1.8.1-restored"
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

All benchmarks are verified by `test_cases.py` before every commit.

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

A bridge (`ros2_bridge.py`) is included in the repository. It runs standalone
with no ROS 2 installation required and becomes a full publisher/subscriber node
when `rclpy` is present, publishing on three dedicated topics:

- `/qerra/ethical_score` — `Float32`, numerical risk score
- `/qerra/ethical_decision` — `Bool`, True = safe to proceed
- `/qerra/semev12_result` — `String`, full JSON assessment

See [`QERRA_FOR_ROBOTICS.md`](./QERRA_FOR_ROBOTICS.md) for full integration
details and open questions for the robotics community.

---

## Repository Structure

```
├── ethical_core.py                      # SEMEV-12 scoring engine (v1.8.1)
├── vectors.py                           # Immutable vector definitions and weights
├── app.py                               # FastAPI application
├── ros2_bridge.py                       # ROS 2 bridge (standalone + rclpy node)
├── test_cases.py                        # Regression test suite
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

**Version:** `1.8.1-restored`
**Stage:** Stable core engine with active development on ROS 2 integration
and nuance refinement.

The ethical scoring engine is stable and calibrated. The API is protected,
rate-limited, and fully documented. Canonical benchmarks are regression-tested.
The project is actively seeking real-world integration and community feedback.

**Known limitations:**

- The current engine actively implements and scores **5 of the 12 SEMEV-12 vectors** (v003, v004, v005, v007, v010). The remaining 7 vectors are defined in the framework and reserved for future releases.
- Hybrid detection means highly indirect or heavily implicit language may not activate all relevant vectors.
- This is a research and integration tool, not a certified clinical, legal, or production safety system.

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

## License

AGPL-3.0 — see `LICENSE` for full terms.
Commercial licensing available on request.

*QERRA-v2 Classical — ethical conscience as the foundation of every decision.*
