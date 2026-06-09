# LIMITATIONS of QERRA-v2 Classical

This is an early research prototype, not a production or clinical tool.

### Current Technical Limitations
- While 7 vectors use full semantic similarity (all-MiniLM-L6-v2) and 5 have now been upgraded from pure regex to semantic detection (v1.9.0), the system can still miss highly nuanced, indirect, sarcastic, or culturally-specific expressions.
- Detection quality depends on the quality of the vector descriptions and current thresholds, which were calibrated on a limited set of test cases.
- The system does not have the deep contextual understanding or world knowledge of large language models.
- Scores and decisions are fully explainable and deterministic but remain simplified approximations of complex real-world ethical situations.
- The public API runs on the Hugging Face free tier, which can have uptime and latency limitations.

### ROS 2 Integration Limitations
- The hybrid Action Server (remote API with 800ms local CPU fallback) has been tested but not yet deployed on real edge hardware (Jetson, Raspberry Pi, etc.) under full robotic workloads.
- The PyTrees Condition Node is functional but has only been tested in simulation and standalone mode.

### Important Ethical Note
QERRA-v2 Classical is a research tool designed to support ethical reflection and safer autonomous systems.  
It is **not** a substitute for professional human judgment, therapy, legal advice, or certified safety systems.  
Any output should be treated as one source of information among many and always reviewed by responsible humans.

### Intended Use
- Research and experimentation
- Educational purposes
- Exploration of structured, explainable ethical reasoning in robotics and AI
- Development of Behavior Tree safety layers

We welcome feedback, rigorous testing, and contributions — especially on detection robustness, cross-cultural validation, and real-world robotics integration.

**Last updated:** June 2026
