# =====================================================
# QERRA-v2 Classical Edition - Main API
# High-Quality 100% Classical Ethical Framework
# =====================================================

import os
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Security, Request
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address

from classical_analyze import analyze_text
from vectors import get_sacred_vectors
from utils.response import api_response
from models.input import AnalyzeRequest
from auth.api_key import require_api_key   # ← NEW IMPORT

load_dotenv()

# Rate limiter setup
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="QERRA-v2 Classical",
    description="100% Classical High-Quality Ethical Decision Framework",
    version="1.7-classical-nuance-calibrated"
)

app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/analyze", dependencies=[Depends(require_api_key)])
@limiter.limit("20/minute")
def analyze(request: Request, data: AnalyzeRequest):
    """Main classical ethical analysis endpoint with rate limiting + API key."""
    result = analyze_text(data.text)
    return api_response(result)


@app.get("/")
def home():
    return api_response({
        "status": "QERRA-v2 Classical Edition is live",
        "message": "High-quality 100% classical ethical decision engine",
        "note": "This is the classical counterpart of the main hybrid QERRA-v2 project"
    })


@app.get("/health")
def health():
    """Simple health check - no API key required."""
    vectors = get_sacred_vectors()
    return api_response({
        "status": "healthy",
        "vectors_loaded": len(vectors),
        "framework": "QERRA-v2 Classical Edition",
        "note": "All 12 SEMEV-12 core vectors are active"
    })


@app.get("/vectors")
def get_vectors():
    """Return all SEMEV-12 vector definitions - no API key required."""
    vectors = get_sacred_vectors()
    return api_response({
        "framework": "SEMEV-12",
        "description": "12 foundational ethical vectors for human-centred decision making",
        "vectors": vectors,
        "note": "This endpoint makes the ethical framework fully inspectable and auditable"
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
