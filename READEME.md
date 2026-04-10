# QERRA-v2 Classical Edition

**100% Classical Ethical Decision Framework**  
Clean, fast, and high-quality classical counterpart of the main QERRA-v2 hybrid project.

### Purpose
- Pure classical ethical scoring engine
- Uses sacred vectors (loaded from `src/vectors.py`)
- Designed for maximum stability, explainability and ease of testing
- Ideal for early collaborators, testers and workshops

### How to run locally
```bash
pip install -r requirements.txt
uvicorn app:app --reload --port 8000