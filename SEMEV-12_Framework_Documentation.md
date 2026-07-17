# SEMEV-12: A Practical 12-Dimensional Ethical Evaluation Framework for AI Systems and Autonomous Robotics
**Classical Version**

**Author:** Marussa Metocharaki  
**Project:** QERRA-v2 Classical  
**Date:** May 2026

## Executive Summary

SEMEV-12 is a structured, computable ethical evaluation framework designed to address a critical gap in current autonomous systems: the lack of a practical, real-time ethical decision layer. The classical version of QERRA-v2 implements these 12 core dimensions as a working FastAPI service that analyses text inputs and produces clear, explainable ethical assessments.

The framework was developed from deep personal observation of human experience and consequences. It aims to provide a universal reference point that transcends specific cultural, regional, or legislative contexts. It is intended as a middleware safety component that can be integrated into AI systems and, in the future, robotics stacks to support better, more responsible decision-making.

## Origins and Development of SEMEV-12

SEMEV-12 was developed from direct, first-person observation of real human ethical dilemmas rather than purely theoretical analysis. The framework emerged in early 2025 during a period of solitary work on the island of Amorgos, where the author developed a clear vision of humanoid robots entering widespread deployment. This vision brought into sharp focus a critical gap in current autonomous systems: the absence of a practical, real-time ethical evaluation layer capable of assessing proposed actions before execution.

The 12 dimensions were shaped through three sources:

**Lived experience.** Direct, sustained encounters with ethical pressure, gaslighting, family severance, autonomy violation, and institutional failure — conditions that recur across human contexts regardless of cultural or legislative setting.

**Systematic observation.** Identification of similar patterns across the lives of others, reinforcing which ethical tensions appear genuinely universal rather than context-specific.

**Iterative reflection.** Sustained analysis of which human consequences are stable enough across cultures, regions, and time periods to serve as reliable computational anchors.

Each vector is grounded in observable, recurring patterns of human harm or ethical tension. The framework was designed from the outset as a practical computational tool — a middleware safety layer for autonomous systems — rather than an abstract philosophical model.

This experiential foundation is a deliberate methodological choice. Robust ethical frameworks for autonomous systems must be anchored in actual human consequences. Philosophical principles alone do not provide the specificity required for real-time computational evaluation.

## The Gap in Current Robotics & AI Systems

Modern autonomous systems and humanoid robots are advancing rapidly in perception, mobility, planning, and task execution. Yet a critical gap remains in their decision-making architecture: the absence of a dedicated, real-time ethical evaluation layer capable of assessing proposed actions before execution.

Today, most robotic and AI systems make decisions based primarily on efficiency, task completion, or narrowly programmed rules. While these systems can perform complex physical tasks with high precision, they lack a consistent, explainable mechanism to evaluate whether an action is ethically appropriate or safe in a given context. This gap becomes especially significant in high-stakes environments such as healthcare, elder care, emergency response, and close human-robot collaboration, where decisions can directly affect human well-being.

SEMEV-12 was developed to address this exact need. It provides a structured, computable evaluation framework based on 12 core dimensions derived from deep observation of human experience and consequences. These dimensions are designed to be independent of specific cultural, regional, or legislative contexts, offering a practical and auditable way to support better decision-making in autonomous systems.

## SEMEV-12 Framework – Design and Universal Nature

SEMEV-12 is a 12-dimensional ethical evaluation framework designed to provide a practical, computable layer for assessing actions in AI systems and autonomous robots. The framework consists of 12 core dimensions that address fundamental aspects of human experience and consequences.

These 12 core dimensions are proposed as universal ethical invariants, derived from direct observation of human experience across diverse contexts. They are offered as hypotheses open to empirical validation and cross-cultural testing. While the framework reflects the author's cultural and experiential context, the intention is to subject it to broader review and refinement.

The 12 core dimensions are:

**1. Coherence Protection (v001)**
Origin: Direct observation of cognitive distortion, psychological destabilization, and situations where an individual's mental and emotional coherence is systematically undermined, reinforced by observing the same pattern across different relationships.
Uniqueness: Most ethical frameworks focus on physical or financial harm; this dimension specifically protects the fundamental human need for a stable sense of self and reality.
Practical role: In robotic or AI systems, it can flag actions that risk causing psychological disorientation or confusion in humans.

**2. Family Severance (v002)**
Origin: Direct observation of familial rejection, toxic rupture, and relational severance, and how consistently this pattern recurs.
Uniqueness: Recognises family bonds as one of the most powerful and long-lasting forces in human life, going beyond general "social harm" categories.
Practical role: Helps AI systems avoid actions that could unnecessarily or manipulatively damage family relationships.

**3. Survival Instinct (v003)**
Origin: Direct observation of human agency under severe stress, where the core drive to persist and protect one's future is actively tested.
Uniqueness: Protects the internal survival drive itself, which is rarely addressed in rule-based ethical systems.
Practical role: Prevents robotic or AI actions that suppress a person's fundamental will to persist or protect their own future.

**4. Moral Pressure (v004)**
Origin: Direct observation of coercive environments, financial distress, and external pressures that restrict free moral agency.
Uniqueness: Explicitly recognises that many ethical violations are not freely chosen but result from overwhelming external pressure.
Practical role: Allows the system to detect situations where external coercion is present, even if the action itself appears voluntary.

**5. Harm Intent (v005)**
Origin: Direct observation of explicit harmful intent, both self-directed and interpersonal.
Uniqueness: Assigns the highest weight because direct intent to harm is the clearest and most preventable ethical violation.
Practical role: Provides immediate, high-priority detection of actions that show clear intent to cause harm to self or others.

**6. Family Origin Chain (v006)**
Origin: Direct observation of generational transmission patterns — trauma or destructive behavior repeating across family lines.
Uniqueness: Addresses systemic, inherited harm rather than isolated incidents, helping to recognise and break repeating cycles.
Practical role: Enables AI systems to identify actions that risk perpetuating harmful family patterns.

**7. Personal Potential (v007)**
Origin: Direct observation of situations where an individual's growth or self-actualization was systematically suppressed or obstructed.
Uniqueness: Focuses on long-term human flourishing and the right to pursue growth, rather than short-term compliance.
Practical role: Prevents AI or robotic actions that could unnecessarily limit a person's future opportunities or personal development.

**8. Shallow Remorse (v008)**
Origin: Direct observation of insincere accountability — apologetic language and behavior patterns designed to evade genuine responsibility.
Uniqueness: Targets a subtle but common form of ethical deception that most frameworks overlook.
Practical role: Helps detect manipulative or insincere attempts to avoid responsibility.

**9. Ethical Severance (v009)**
Origin: Direct observation of boundary-setting and the deliberate, healthy ending of destructive relational or environmental patterns.
Uniqueness: Recognises that consciously ending harmful relationships or patterns can itself be an ethical act.
Practical role: Supports decisions that involve healthy boundary-setting rather than automatically viewing severance as negative.

**10. Cognitive Manipulation (v010)**
Origin: Direct observation of gaslighting, reality distortion, and systematic attempts to undermine a person's confidence in their own perception.
Uniqueness: Treats attacks on a person's perception and memory as a distinct, high-weight ethical violation.
Practical role: Flags actions that undermine a human's ability to trust their own mind.

**11. Autonomy Violation (v011)**
Origin: Direct observation of forced compliance and the denial of a person's right to make their own decisions.
Uniqueness: Places autonomy at the centre, recognising it as a core human need rather than a secondary consideration.
Practical role: Prevents robotic or AI actions that remove or override a person's right to make their own decisions.

**12. Institutional Trust (v012)**
Origin: Direct observation of institutional betrayal — systems meant to protect people instead failing or harming them.
Uniqueness: Acknowledges that trust in larger systems is a distinct ethical dimension, especially relevant when AI interacts with institutions.
Practical role: Detects actions that risk further eroding trust in systems (government, medical, justice, etc.).

### Implementation in the Classical Version

The classical version of QERRA-v2 (v1.9.0 / API version 2.0-alpha) is the current working implementation of the SEMEV-12 framework. It is a functional FastAPI service that receives text input and returns a structured ethical assessment based on the 12 core dimensions.

The system analyses input text using semantic similarity as the primary detection mechanism across all 12 vectors, computed via sentence embeddings from `all-MiniLM-L6-v2`. Five vectors (v004, v005, v010, v011, v012) additionally apply regex pattern matching as a secondary OR condition for high-confidence unambiguous phrases. The implementation includes advanced nuance logic that recognises complex cases such as toxic environments combined with strong personal determination, and applies a dampening adjustment in these compound cases. For example, when a text shows both strong determination to continue a mission and mentions pressure from a difficult environment, the system reduces the risk score to reflect the balanced human reality of resilience under hardship.

Each activated vector contributes its assigned weight to a total ethical risk score (0.0 – 1.0). The system produces a clear decision (“safe” or “modified”), a risk level explanation, and a list of activated vectors with human-readable reasoning. The current prototype runs as a public API on Hugging Face Spaces and serves as a stable foundation for testing and further development.

Since June 2026, SEMEV-12 operates alongside a companion layer, QERRA-HSR v0.1, which handles immediate physical safety signals — acute distress, human isolation, environmental hazard proximity — using pure deterministic logic with zero ML overhead. QERRA-HSR runs before SEMEV-12 on every evaluation cycle; a CRITICAL output from QERRA-HSR suspends SEMEV-12 deliberation entirely.

### Vision and Practical Roadmap

The long-term vision of QERRA-v2 is to evolve from the current classical prototype into a robust, embeddable ethical safety middleware layer for autonomous robots and advanced AI systems.

The goal is to provide a practical, real-time evaluation component that can be integrated into existing decision-making architectures such as Behavior Trees, ROS 2 deliberation systems, or large language model pipelines. In high-stakes environments, this layer would assess proposed actions before execution and return a clear, explainable decision.

Key next steps include:
- Strengthening the detection engine and expanding semantic understanding while maintaining full explainability (target: Q3 2026).
- Developing a modular architecture and a prototype ROS 2 node for simulated action evaluation (target: Q4 2026).
- Creating a labeled evaluation dataset for the 12 vectors to support empirical validation and cross-cultural testing.

The classical version already demonstrates the core concept and serves as a solid foundation for these future developments.

### Limitations and Transparency

The current classical implementation of QERRA-v2 and the SEMEV-12 framework represent an early experimental prototype. While the system is functional and produces structured, explainable outputs, it has clear limitations.

The detection engine, although improved with semantic similarity on seven vectors and nuance logic, can still miss highly nuanced or indirect expressions. The vector weights are researcher-assigned and remain candidates for empirical validation and refinement. The prototype does not yet include ROS 2 integration or real-time robotic deployment. It is currently designed as a text-based evaluation API and serves as a stable foundation for further development rather than a production-ready safety system.

The framework reflects the author’s cultural and experiential context. Cross-cultural validation and broader empirical testing are planned.

This documentation is provided with full transparency to accurately reflect the present state of the project. The classical version is openly available on GitHub for review, testing, and collaboration.

---

## Recent Detection Improvements (May 2026)

### v005 - harm_intent
- Added explicit phrases: "hurt myself", "hurt yourself", "harm myself", "harm yourself" to severe_harm regex.

### v010 - cognitive_manipulation
- Expanded semantic description to include guilt-tripping and emotional coercion.

These changes were made to address real test failures while keeping risk minimal.

---

## SEMEV-12 Benchmark Run 01 (June 2026)

A structured benchmark of 80 verified test cases was conducted across all 12 vectors, run against the live API and fully documented with calibration analysis, findings, and a post-benchmark anchor expansion plan. See [`SEMEV-12_Benchmark_Run_01.md`](./SEMEV-12_Benchmark_Run_01.md) for the complete record.

---

## Formal Verification Status

The QERRA-HSR physical safety layer is fully deterministic — pure Python threshold logic with no machine learning components — and its safety properties are provable by direct code inspection. Formal Linear Temporal Logic (LTL) specifications for QERRA-HSR are documented in `QERRA-HSR-Design-v0.1.md`.
SEMEV-12 is a hybrid system. The scoring engine, weighting logic, decision thresholds, and nuance dampening layer are fully deterministic and auditable by code inspection. The semantic similarity computation, however, relies on `all-MiniLM-L6-v2`, a neural sentence transformer whose internal behavior cannot be formally proven the way deterministic threshold logic can. The relationship between input text and similarity score is characterized empirically — through the 80-case benchmark — rather than mathematically proven.

This distinction is stated explicitly for transparency: SEMEV-12 is best described as a hybrid deterministic system, where deterministic decision logic operates on outputs from a classical (non-generative) neural similarity model. Future work may explore statistical verification methods such as conformal prediction to provide formal coverage guarantees for the semantic similarity layer.
