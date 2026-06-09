# LIMITATIONS of QERRA-v2 Classical

This is an early research prototype, not a production or clinical tool.
It is designed for research, experimentation, and structured ethical reasoning
in autonomous systems — not for deployment in safety-critical environments
without further validation.

---

### Current Technical Limitations

**Detection quality**
- 7 of 12 SEMEV-12 vectors use full semantic similarity via `all-MiniLM-L6-v2`.
- The remaining 5 vectors (v001 emotional_distress, v002 family_severance, 
  v006 family_origin_chain, v008 shallow_remorse, v009 ethical_severance) 
  still rely on regex/pattern matching. These are brittle and will miss 
  semantically equivalent expressions that do not match the exact phrases. 
  **This is the highest priority technical gap.**
- The system can miss nuanced, indirect, sarcastic, culturally-specific, 
  or metaphorical language.
- Similarity thresholds were calibrated on a small set of 8 test cases.

**Scoring and robustness**
- The weighted ethical risk score is fully explainable and deterministic 
  but remains a simplified approximation of complex human situations.
- No adversarial robustness testing has been done yet.
- Nuance dampening logic exists but is rule-based.

**Deployment & Integration**
- The hybrid Action Server (v2.0) with 800ms remote timeout + local CPU fallback 
  (~31ms) works in testing, but has not been validated on real edge hardware 
  or physical robots.
- ROS 2 / PyTrees integration is functional in simulation but not yet 
  deployed in real robotic environments.

**Project constraints**
- Solo-developed with zero institutional support, zero funding, and very 
  limited resources.
- All architectural knowledge currently lives with the single author.
- Regression test suite covers only 8 canonical cases.

---

### Important Ethical Note

QERRA-v2 Classical is a research tool designed to support structured ethical 
reflection and safer autonomous systems.

It is **not** a substitute for professional human judgment, therapy, legal 
advice, or certified safety systems. Any output should always be reviewed by 
responsible humans.

---

### Intended Use

- Research and experimentation in explainable ethical reasoning
- Educational exploration of classical AI safety
- Prototyping ethical gates in ROS 2 Behavior Trees

---

We welcome honest feedback, especially on improving detection for the 5 regex-based vectors, adversarial testing, and real-world robotics integration.

*Last updated: June 2026*
