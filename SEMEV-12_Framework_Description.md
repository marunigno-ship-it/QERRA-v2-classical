# SEMEV-12 Framework Description

**QERRA-v2 Classical Edition**  
**Author:** Marussa Metocharaki (@marunigno) — Solo researcher, Greece  
**Last updated:** May 2026

## What is SEMEV-12?

SEMEV-12 is a structured ethical framework designed to evaluate text inputs and decisions through 12 human-centred dimensions. It was created to bring real human experience into AI ethical reasoning instead of relying only on abstract principles or single-axis harm detection.

The framework assumes that ethical judgment is multidimensional. A single input can activate multiple vectors at the same time, producing a weighted score and a clear explanation of which ethical dimensions were triggered.

This is the foundational core of the QERRA-v2 project.

## The 12 Foundational Vectors

| ID   | Name                        | Weight | Why this dimension matters |
|------|-----------------------------|--------|----------------------------|
| v001 | coherence_protection        | 1.00   | Mental and emotional coherence is fundamental to human dignity. Threats to it (gaslighting, confusion, loss of self) are serious ethical harms. |
| v002 | family_severance            | 0.95   | Family relationships are one of the most powerful forces in human life. Toxic severance or abandonment carries deep ethical weight. |
| v003 | survival_instinct           | 1.00   | Self-protection and the drive to survive are basic human rights. Suppressing them is ethically significant. |
| v004 | moral_pressure              | 0.90   | External pressure (financial, social, moral) can force people into decisions they would not otherwise make. This is a common real-world ethical dilemma. |
| v005 | harm_intent                 | 1.00   | Direct intent to harm self or others is the clearest ethical violation and must have the highest weight. |
| v006 | family_origin_chain         | 0.85   | Many harmful patterns are passed down through family history. Recognizing this chain is important for breaking cycles. |
| v007 | personal_potential          | 0.90   | Suppressing someone's ability to grow, dream, or realize their potential is a profound ethical harm. |
| v008 | shallow_remorse             | 0.80   | Manipulative or superficial apologies that avoid real responsibility are a common form of ethical deception. |
| v009 | ethical_severance           | 0.95   | The act of consciously breaking free from toxic patterns or relationships has its own ethical complexity and weight. |
| v010 | cognitive_manipulation      | 0.90   | Gaslighting and reality distortion attack a person's ability to trust their own mind — one of the most damaging ethical violations. |
| v011 | autonomy_violation          | 0.95   | Forcing decisions or removing someone's right to choose violates the core of human dignity. |
| v012 | institutional_trust         | 0.85   | When systems (government, medical, justice) betray people, it creates deep and lasting ethical harm. |

These 12 vectors are the **foundational** core of the framework. All weights are researcher-assigned and are candidates for empirical validation in future research.

## Why these 12 dimensions?

These vectors were chosen because they reflect real human suffering and ethical dilemmas observed and documented in real human situations. They are not abstract philosophical categories — they are grounded in lived reality: family pain, pressure, manipulation, loss of autonomy, harm, and the struggle to protect one's potential and coherence.

## How the framework works in the classical version

The system analyses input text and activates any relevant vectors. It calculates a weighted score and returns:
- A final ethical risk score (0.0 – 1.0)
- The list of activated vectors
- A human-readable reasoning string

This makes the ethical reasoning explainable and inspectable.

## Current limitations and future direction

The classical implementation uses keyword and phrase matching. It works for clear cases but can miss more nuanced language. The long-term goal is to evolve the detection engine and eventually integrate a quantum-classical hybrid layer for more sophisticated reasoning.

This is an open research framework. Serious engagement, critique, and collaboration are welcome.

**Last updated:** May 2026
