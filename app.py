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

from src.classical_analyze import analyze_text
from src.vectors import get_sacred_vectors

load_dotenv()

# Rate limiter setup
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="QERRA-v2 Classical",
    description="100% Classical High-Quality Ethical Decision Framework",
    version="1.2"
)

app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY_NAME = "x-api-key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

API_KEY = os.getenv("QERRA_API_KEY")

async def verify_api_key(api_key: str = Security(api_key_header)):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="Server API key not configured.")
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return api_key

class AnalyzeRequest(BaseModel):
    text: str

    model_config = {"str_strip_whitespace": True}

    @field_validator("text")
    def text_must_not_be_empty(cls, v):
        if len(v.strip()) < 3:
            raise ValueError("Text too short")
        if len(v) > 5000:
            raise ValueError("Text too long")
        return v


@app.post("/analyze", dependencies=[Depends(verify_api_key)])
@limiter.limit("20/minute")
def analyze(request: Request, data: AnalyzeRequest):
    """Main classical ethical analysis endpoint with rate limiting."""
    result = analyze_text(data.text)
    return result


@app.get("/")
def home():
    return {
        "status": "QERRA-v2 Classical Edition is live",
        "message": "High-quality 100% classical ethical decision engine",
        "note": "This is the classical counterpart of the main hybrid QERRA-v2 project"
    }


# === NEW: Health endpoint (Claude Step 3) ===
@app.get("/health")
def health():
    """Simple health check - no API key required."""
    vectors = get_sacred_vectors()
    return {
        "status": "healthy",
        "version": "1.2-classical",
        "vectors_loaded": len(vectors),
        "framework": "QERRA-v2 Classical Edition",
        "note": "All 12 SEMEV-12 core vectors are active"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)