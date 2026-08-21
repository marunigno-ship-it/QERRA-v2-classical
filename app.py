# =====================================================
# QERRA-v2 Classical Edition — Main API
# Version: 2.0.0
# Three-layer architecture:
#   Layer 2 — QERRA-HSR v0.1 (physical safety, pure Python)
#   Layer 1 — SEMEV-12 v1.9.0 (ethical reasoning, semantic)
#   Layer 3 — QERRA-THRIVE v2.0.0 (values companion, action ranker)
# =====================================================

from typing import Optional, List
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address

from classical_analyze import analyze_text
from vectors import get_semev12_vectors
from utils.response import api_response
from auth.api_key import require_api_key

# Layer 2: QERRA-HSR
from hsr.qerra_hsr import evaluate_hsr, HSRInput, HSRStatus

# Layer 3: QERRA-THRIVE Package
import values

load_dotenv()

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="QERRA-v2 Classical",
    description=(
        "Three-layer ethical, physical, and value-based safety middleware. "
        "Layer 2 QERRA-HSR v0.1 (physical safety) + Layer 1 SEMEV-12 v1.9.0 "
        "(moral deliberation) + Layer 3 QERRA-THRIVE v2.0.0 (values action ranker). "
        "Fully deterministic and explainable."
    ),
    version="2.0.0"
)

app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================================
# Layer 1 & 2 Request Models
# =====================================================

class HSRSignals(BaseModel):
    distress_confidence: float       # 0.0–1.0 from robot perception stack
    persons_nearby_count: int        # upright, responsive humans nearby
    hazard_proximity_flag: bool      # confirmed hazard near a human
    robot_task_interruptible: bool   # affects HOW, never WHETHER


class CombinedRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="The situation to evaluate (10–5000 characters)"
    )
    hsr_signals: Optional[HSRSignals] = None   # optional — for QERRA-HSR

    @field_validator("text")
    @classmethod
    def text_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError("Text cannot be empty or only whitespace")
        return v.strip()


# =====================================================
# Layer 3 Request Model
# =====================================================

class RankRequest(BaseModel):
    vector_name: str = Field(
        ...,
        description="The Layer 3 THRIVE vector to evaluate (e.g. 'transparent_disclosure', 'flora_boundary_protection')"
    )
    candidates: List[str] = Field(
        ...,
        min_items=2,
        max_items=10,
        description="List of 2 to 10 candidate action text strings to rank"
    )


# =====================================================
# Main Endpoint — /analyze (Layers 1 & 2)
# =====================================================

@app.post("/analyze", dependencies=[Depends(require_api_key)])
@limiter.limit("20/minute")
def analyze(request: Request, data: CombinedRequest):
    """
    Two-layer ethical and physical safety evaluation (SEMEV-12 + QERRA-HSR).
    """
    hsr_result_payload = None
    semev12_suspended = False

    if data.hsr_signals is not None:
        hsr_input = HSRInput(
            distress_confidence=data.hsr_signals.distress_confidence,
            persons_nearby_count=data.hsr_signals.persons_nearby_count,
            hazard_proximity_flag=data.hsr_signals.hazard_proximity_flag,
            robot_task_interruptible=data.hsr_signals.robot_task_interruptible,
        )

        hsr_result = evaluate_hsr(hsr_input)

        hsr_result_payload = {
            "status": hsr_result.status.value,
            "vectors_activated": hsr_result.vectors_activated,
            "reasoning": hsr_result.reasoning,
            "version": hsr_result.version,
        }

        if hsr_result.status == HSRStatus.CRITICAL:
            semev12_suspended = True
            return api_response({
                "hsr": hsr_result_payload,
                "semev12_suspended": semev12_suspended,
                "suspended_instruction": data.text,
                "data": {},
                "note": (
                    "QERRA-HSR returned CRITICAL. "
                    "SEMEV-12 ethical evaluation suspended. "
                    "Physical safety response required immediately."
                )
            })

    semev12_result = analyze_text(data.text)

    return api_response({
        "hsr": hsr_result_payload,
        "semev12_suspended": semev12_suspended,
        "data": semev12_result,
    })


# =====================================================
# Layer 3 Endpoint — /rank (Action Ranker)
# =====================================================

@app.post("/rank", dependencies=[Depends(require_api_key)])
@limiter.limit("20/minute")
def rank_actions(request: Request, data: RankRequest):
    """
    Layer 3 (QERRA-THRIVE) Action Ranking Endpoint.
    Evaluates candidate action text choices against the specified THRIVE vector.
    """
    func_name = f"rank_{data.vector_name}" if not data.vector_name.startswith("rank_") else data.vector_name
    ranker_func = getattr(values, func_name, None)

    if ranker_func is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown Layer 3 vector '{data.vector_name}'. Available: {values.ALL_THRIVE_VECTORS}"
        )

    try:
        result = ranker_func(data.candidates)
        return api_response({
            "framework": "QERRA-THRIVE Layer 3",
            "version": "2.0.0",
            "result": result
        })
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Layer 3 execution error on vector '{data.vector_name}': {str(e)}"
        )


# =====================================================
# Public Endpoints
# =====================================================

@app.get("/")
def home():
    return api_response({
        "status": "QERRA-v2 Classical Edition is live",
        "message": "Three-layer ethical, physical, and value-based safety middleware",
        "layers": {
            "qerra_hsr": "Layer 2 — Physical safety — v0.1 — 3 vectors pure Python",
            "semev12": "Layer 1 — Moral deliberation — v1.9.0 — 12 vectors semantic",
            "qerra_thrive": "Layer 3 — Value action ranker — v2.0.0 — 12 vectors hybrid"
        },
        "note": "Fully explainable three-layer middleware for robotics and autonomous AI systems."
    })


@app.get("/health")
def health():
    vectors = get_semev12_vectors()
    return api_response({
        "status": "healthy",
        "semev12_vectors_loaded": len(vectors),
        "thrive_vectors_loaded": len(values.ALL_THRIVE_VECTORS),
        "framework": "QERRA-v2 Classical Edition",
        "semev12_version": "1.9.0",
        "qerra_hsr_version": "0.1",
        "qerra_thrive_version": "2.0.0",
    })


@app.get("/thrive/vectors")
def get_thrive_vectors():
    """
    Return all 12 QERRA-THRIVE Layer 3 vector names and suite breakdowns.
    """
    return api_response({
        "framework": "QERRA-THRIVE",
        "version": "2.0.0",
        "total_vectors": len(values.ALL_THRIVE_VECTORS),
        "suites": {
            "human_centered_suite_a": values.HUMAN_CENTERED_VECTORS,
            "ecological_suite_b": values.ECOLOGICAL_VECTORS,
        },
        "all_vectors": values.ALL_THRIVE_VECTORS,
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
