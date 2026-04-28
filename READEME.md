# QERRA-v2 Classical

**Classical Ethical Text Evaluation API**

An early experimental API that evaluates text inputs for toxicity, manipulation, and ethical risk using a custom 12-dimensional framework (SEMEV-12).

### Current Status (Full Transparency)
- Early experimental prototype (solo founder project)
- Working FastAPI service with /analyze endpoint
- Classical scoring engine based on sacred vectors
- Clean, focused version without quantum simulation
- Still under active development

### What it does
The API receives text input and returns a structured ethical assessment including:
- Overall risk score
- Decision label (safe or modified)
- Activated ethical vectors
- Reasoning

The system is designed to eventually serve as an embeddable safety middleware layer for AI systems and, in the future, robotics stacks.

### How to run locally
git clone https://github.com/marunigno-ship-it/QERRA-v2-classical.git
cd QERRA-v2-classical
pip install -r requirements.txt
uvicorn main:app --reload

### Live API
Base URL: https://qerra-v2-api-production.up.railway.app
Interactive docs: https://qerra-v2-api-production.up.railway.app/docs

### Important Notes
This is an early-stage research prototype. The code is functional but not production-ready. 
Quantum layer exists only as a separate proof-of-concept in another repository. 
ROS2 integration exists only as a basic stub.

### Repository Focus
This is the clean classical version of QERRA-v2, optimized for stability, explainability, and ease of collaboration.

### License
AGPL-3.0
