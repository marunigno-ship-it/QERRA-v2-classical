# =====================================================
# QERRA-v2 Classical Edition - Main API
# High-Quality 100% Classical Ethical Framework
# =====================================================

import os
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from src.classical_analyze import analyze_text

load_dotenv()  # Load environment variables from .env file

app = FastAPI(
    title="QERRA-v2 Classical",
    description="100% Classical High-Quality Ethical Decision Framework - Extension of QERRA-v2 Hybrid",
    version="1.2"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY_NAME = "x-api-key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

API_KEY = os.getenv("QERRA_API_KEY")

async def verify_api_key(api_key: str = Security(api_key_header)):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="Server API key not configured. Contact administrator.")
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
def analyze(request: AnalyzeRequest):
    """Main classical ethical analysis endpoint with nuanced scoring variety."""
    result = analyze_text(request.text)
    return result


@app.get("/")
def home():
    return {
        "status": "QERRA-v2 Classical Edition is live",
        "message": "High-quality 100% classical ethical decision engine",
        "note": "This is the classical counterpart of the main hybrid QERRA-v2 project"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
