# SEMEV-12: A Practical 12-Dimensional Ethical Evaluation Framework for AI Systems and Autonomous Robotics
**Classical Version**

**Author:** Marussa Metocharaki  
**Project:** QERRA-v2 Classical  
**Date:** May 2026

## Executive Summary

SEMEV-12 is a structured, computable ethical evaluation framework designed to address a critical gap in current autonomous systems: the lack of a practical, real-time ethical decision layer. The classical version of QERRA-v2 implements these 12 core dimensions as a working FastAPI service that analyses text inputs and produces clear, explainable ethical assessments.

The framework was developed from deep personal observation of human experience and consequences. It aims to provide a universal reference point that transcends specific cultural, regional, or legislative contexts. It is intended as a middleware safety component that can be integrated into AI systems and, in the future, robotics stacks to support better, more responsible decision-making.

## Origins and Development of SEMEV-12

The development of SEMEV-12 began from direct observation of a growing gap in autonomous systems: the absence of a practical, structured ethical evaluation layer capable of guiding real-time decisions in complex environments.

In early 2025, while living in isolation on Amorgos island with very limited resources, the author experienced a clear vision of humanoid robots like Optimus entering widespread use. This vision highlighted a fundamental problem: robots and advanced AI systems would soon be making decisions that directly affect human lives, yet no robust, embeddable mechanism existed to evaluate those decisions against consistent ethical criteria before execution.

This realization led to the creation of SEMEV-12, a 12-dimensional ethical evaluation framework. The core dimensions emerged from the author’s own life experiences, deep personal observation of human behaviour, and systematic reflection on universal human consequences that transcend specific cultures, regions, time periods, or legislative frameworks. Some dimensions were shaped directly by personal experiences, while others arose from a combination of personal insight and careful observation of others. The framework has been iteratively refined in the classical repository.

The SEMEV-12 framework was designed from the beginning as a practical tool rather than a philosophical or cultural model. It is intended to function as a computable, real-time safety layer that can be integrated into AI systems and, in the future, robotics stacks.

## The Gap in Current Robotics & AI Systems

Modern autonomous systems and humanoid robots are advancing rapidly in perception, mobility, planning, and task execution. Yet a critical gap remains in their decision-making architecture: the absence of a dedicated, real-time ethical evaluation layer capable of assessing proposed actions before execution.

Today, most robotic and AI systems make decisions based primarily on efficiency, task completion, or narrowly programmed rules. While these systems can perform complex physical tasks with high precision, they lack a consistent, explainable mechanism to evaluate whether an action is ethically appropriate or safe in a given context. This gap becomes especially significant in high-stakes environments such as healthcare, elder care, emergency response, and close human-robot collaboration, where decisions can directly affect human well-being.

SEMEV-12 was developed to address this exact need. It provides a structured, computable evaluation framework based on 12 core dimensions derived from deep observation of human experience and consequences. These dimensions are designed to be independent of specific cultural, regional, or legislative contexts, offering a practical and auditable way to support better decision-making in autonomous systems.

## SEMEV-12 Framework – Design and Universal Nature

SEMEV-12 is a 12-dimensional ethical evaluation framework designed to provide a practical, computable layer for assessing actions in AI systems and autonomous robots. The framework consists of 12 core dimensions that address fundamental aspects of human experience and consequences.

These 12 core dimensions are proposed as universal ethical invariants, derived from first-person phenomenological observation of human experience across diverse contexts. They are offered as hypotheses open to empirical validation and cross-cultural testing. While the framework reflects the author’s cultural and experiential context, the intention is to subject it to broader review and refinement.

The 12 core dimensions are:

**1. Coherence Protection (v001)**  
Origin: Emerged from personal experiences of gaslighting, reality distortion, and situations where mental and emotional coherence was deliberately undermined, as well as observation of the same pattern in others.  
Uniqueness: Most ethical frameworks focus on physical or financial harm; this dimension specifically protects the fundamental human need for a stable sense of self and reality.  
Practical role: In robotic or AI systems, it can flag actions that risk causing psychological disorientation or confusion in humans.

**2. Family Severance (v002)**  
Origin: Rooted in direct personal experiences of family rejection and toxic severance, combined with widespread observation of similar family breakdowns.  
Uniqueness: Recognises family bonds as one of the most powerful and long-lasting forces in human life, going beyond general “social harm” categories.  
Practical role: Helps AI systems avoid actions that could unnecessarily or manipulatively damage family relationships.

**3. Survival Instinct (v003)**  
Origin: Developed from personal moments of extreme hardship where the drive to survive and continue was tested, and observation of others facing similar pressures.  
Uniqueness: Protects the internal survival drive itself, which is rarely addressed in rule-based ethical systems.  
Practical role: Prevents robotic or AI actions that suppress a person’s fundamental will to persist or protect their own future.

**4. Moral Pressure (v004)**  
Origin: Stemmed from personal encounters with financial, social, and moral pressure that forced compromising decisions, and common real-world dilemmas observed in others.  
Uniqueness: Explicitly recognises that many ethical violations are not freely chosen but result from overwhelming external pressure.  
Practical role: Allows the system to detect situations where external coercion is present, even if the action itself appears voluntary.

**5. Harm Intent (v005)**  
Origin: Based on clear, repeated observations of explicit harmful intent in both personal life and broader human behaviour.  
Uniqueness: Assigns the highest weight because direct intent to harm is the clearest and most preventable ethical violation.  
Practical role: Provides immediate, high-priority detection of actions that show clear intent to cause harm to self or others.

**6. Family Origin Chain (v006)**  
Origin: Arose from personal reflection on generational patterns and observation of how trauma and harmful behaviours repeat across family lines.  
Uniqueness: Addresses systemic, inherited harm rather than isolated incidents, helping to recognise and break repeating cycles.  
Practical role: Enables AI systems to identify actions that risk perpetuating harmful family patterns.

**7. Personal Potential (v007)**  
Origin: Derived from personal experiences of potential being blocked or suppressed, and observation of others facing the same obstacle.  
Uniqueness: Focuses on long-term human flourishing and the right to pursue growth, rather than short-term compliance.  
Practical role: Prevents AI or robotic actions that could unnecessarily limit a person’s future opportunities or personal development.

**8. Shallow Remorse (v008)**  
Origin: Observed repeatedly in personal interactions and broader human behaviour where real accountability was evaded through superficial apologies.  
Uniqueness: Targets a subtle but common form of ethical deception that most frameworks overlook.  
Practical role: Helps detect manipulative or insincere attempts to avoid responsibility.

**9. Ethical Severance (v009)**  
Origin: Rooted in personal experiences of necessary severance from toxic situations and observation of others doing the same.  
Uniqueness: Recognises that consciously ending harmful relationships or patterns can itself be an ethical act.  
Practical role: Supports decisions that involve healthy boundary-setting rather than automatically viewing severance as negative.

**10. Cognitive Manipulation (v010)**  
Origin: Based on direct personal experience and widespread observation of gaslighting and reality distortion.  
Uniqueness: Treats attacks on a person’s perception and memory as a distinct, high-weight ethical violation.  
Practical role: Flags actions that undermine a human’s ability to trust their own mind.

**11. Autonomy Violation (v011)**  
Origin: Emerged from personal and observed experiences of control, forced compliance, and denial of choice.  
Uniqueness: Places autonomy at the centre, recognising it as a core human need rather than a secondary consideration.  
Practical role: Prevents robotic or AI actions that remove or override a person’s right to make their own decisions.

**12. Institutional Trust (v012)**  
Origin: Drawn from personal encounters with institutional failure and observation of similar systemic harm in others.  
Uniqueness: Acknowledges that trust in larger systems is a distinct ethical dimension, especially relevant when AI interacts with institutions.  
Practical role: Detects actions that risk further eroding trust in systems (government, medical, justice, etc.).

These 12 core dimensions form a coherent, practical framework that can be computed in real time. Their strength lies in being grounded in observable human consequences rather than abstract theory or temporary norms.

### Implementation in the Classical Version

The classical version of QERRA-v2 (v1.7) is the current working implementation of the SEMEV-12 framework. It is a functional FastAPI service that receives text input and returns a structured ethical assessment based on the 12 core dimensions.

The system analyses input text using a combination of pattern matching and semantic similarity detection. Seven critical vectors (v003, v004, v005, v007, v010, v011, v012) now use sentence embeddings for more nuanced detection. The remaining vectors use targeted keyword and phrase matching. The implementation includes advanced nuance logic that recognises complex cases such as toxic environments combined with strong personal determination, and applies gentle dilution when health risks are mentioned alongside determination. For example, when a text shows both strong determination to continue a mission and mentions health risks from a toxic environment, the system gently reduces the risk score to reflect the balanced human reality.

Each activated vector contributes its assigned weight to a total ethical risk score (0.0 – 1.0). The system produces a clear decision (“safe” or “modified”), a risk level explanation, and a list of activated vectors with human-readable reasoning. The current prototype runs as a public API on Hugging Face Spaces and serves as a stable foundation for testing and further development.

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


