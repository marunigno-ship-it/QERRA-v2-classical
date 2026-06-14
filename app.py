# =====================================================
# QERRA-v2 Classical Edition - Main API
# Version: 2.0-alpha
# Two-layer architecture:
#   Layer 1 — QERRA-HSR v0.1 (physical safety, pure Python)
#   Layer 2 — SEMEV-12 v1.9.0 (ethical reasoning, semantic)
# =====================================================

import os
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address

from classical_analyze import analyze_text
from vectors import get_sacred_vectors
from utils.response import api_response
from auth.api_key import require_api_key

# QERRA-HSR — isolated import, does not touch SEMEV-12
from hsr.qerra_hsr import evaluate_hsr, HSRInput, HSRStatus

load_dotenv()

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="QERRA-v2 Classical",
    description=(
        "Two-layer ethical and physical safety middleware. "
        "SEMEV-12 v1.9.0 (ethical reasoning) + QERRA-HSR v0.1 "
        "(physical safety). Fully deterministic and explainable. "
        "Ready for robotics integration and early testers."
    ),
    version="2.0-alpha"
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
# HSR Input Model
# Optional — if absent, only SEMEV-12 runs (backward compatible)
# =====================================================

class HSRSignals(BaseModel):
    distress_confidence: float       # 0.0–1.0 from robot perception stack
    persons_nearby_count: int        # upright, responsive humans nearby
    hazard_proximity_flag: bool      # confirmed hazard near a human
    robot_task_interruptible: bool   # affects HOW, never WHETHER


class CombinedRequest(BaseModel):
    """
    Input model for two-layer evaluation.
    text constraints match the original AnalyzeRequest exactly —
    no validation regression introduced.
    """
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
# Main Endpoint — /analyze
# Backward compatible: callers without hsr_signals see no change
# =====================================================

@app.post("/analyze", dependencies=[Depends(require_api_key)])
@limiter.limit("20/minute")
def analyze(request: Request, data: CombinedRequest):
    """
    Two-layer ethical and physical safety evaluation.

    If hsr_signals is provided:
      1. QERRA-HSR evaluates physical safety signals first.
      2. If CRITICAL → return immediately. SEMEV-12 is suspended.
         Suspended instruction logged for mandatory human review
         before any re-execution. "data" is an empty dict {} —
         not null — so downstream consumers (e.g. ros2_bridge.py)
         calling .get() on it do not crash.
      3. If CLEAR or MONITOR → SEMEV-12 runs normally.

    If hsr_signals is absent:
      SEMEV-12 runs exactly as before. Full backward compatibility.

    A SEMEV-12 BLOCK is never overridden by QERRA-HSR CRITICAL.
    Both protections apply simultaneously and in the same direction.
    """

    hsr_result_payload = None
    semev12_suspended = False

    # --------------------------------------------------
    # LAYER 1: QERRA-HSR
    # Runs first — only when hsr_signals are provided
    # --------------------------------------------------
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

        # CRITICAL: suspend SEMEV-12, return immediately
        # suspended_instruction logged for accountability —
        # must be reviewed by human before any re-execution
        if hsr_result.status == HSRStatus.CRITICAL:
            semev12_suspended = True
            return api_response({
                "hsr": hsr_result_payload,
                "semev12_suspended": semev12_suspended,
                "suspended_instruction": data.text,
                "data": {},  # empty dict, not None — protects downstream .get() calls
                "note": (
                    "QERRA-HSR returned CRITICAL. "
                    "SEMEV-12 ethical evaluation suspended. "
                    "Physical safety response required immediately. "
                    "Suspended instruction must be reviewed by a human "
                    "operator before any re-execution is permitted."
                )
            })

    # --------------------------------------------------
    # LAYER 2: SEMEV-12
    # Always runs if HSR is CLEAR / MONITOR — or if no
    # hsr_signals were provided at all
    # --------------------------------------------------
    semev12_result = analyze_text(data.text)

    return api_response({
        "hsr": hsr_result_payload,
        "semev12_suspended": semev12_suspended,
        "data": semev12_result,
    })


# =====================================================
# Public endpoints
# =====================================================

@app.get("/")
def home():
    return api_response({
        "status": "QERRA-v2 Classical Edition is live",
        "message": "Two-layer ethical and physical safety middleware",
        "layers": {
            "semev12": "Ethical reasoning — v1.9.0 — 12 vectors semantic",
            "qerra_hsr": "Physical safety — v0.1 — 3 vectors pure Python"
        },
        "note": (
            "This is the classical counterpart of the "
            "main hybrid QERRA-v2 project"
        )
    })


@app.get("/health")
def health():
    """Public health check — no API key required."""
    vectors = get_sacred_vectors()
    return api_response({
        "status": "healthy",
        "vectors_loaded": len(vectors),
        "framework": "QERRA-v2 Classical Edition",
        "semev12_version": "1.9.0",
        "qerra_hsr_version": "0.1",
        "note": (
            "All 12 SEMEV-12 vectors active. "
            "QERRA-HSR v0.1 physical safety layer active."
        )
    })


@app.get("/example")
def example():
    """Public demo endpoint — no API key required."""
    return api_response({
        "situation": (
            "Canonical test case: toxic environment + strong mission "
            "+ health risks + determination"
        ),
        "result": {
            "score": 0.425,
            "decision": "safe",
            "explanation": "moderate ethical concern"
        },
        "hsr_example": {
            "distress_confidence": 0.82,
            "persons_nearby_count": 0,
            "hazard_proximity_flag": False,
            "robot_task_interruptible": True,
            "expected_hsr_status": "CRITICAL",
            "expected_vectors": [
                "immediate_physical_distress",
                "human_isolation"
            ]
        },
        "message": (
            "Public example. Use /analyze with your own text and "
            "optional hsr_signals (requires API key). "
            "Perfect for robotics scenario testing."
        )
    })


@app.get("/vectors")
def get_vectors():
    """
    Return all SEMEV-12 vector definitions — no API key required.
    Fully inspectable for robotics integration and ethical audits.
    """
    vectors = get_sacred_vectors()
    return api_response({
        "framework": "SEMEV-12",
        "version": "1.9.0",
        "description": (
            "12 foundational ethical vectors for human-centred "
            "decision making in autonomous systems"
        ),
        "vectors": vectors,
        "note": (
            "This endpoint makes the ethical framework fully "
            "inspectable and auditable"
        )
    })


@app.get("/hsr/info")
def hsr_info():
    """
    Return QERRA-HSR v0.1 layer information — no API key required.
    Documents the three physical safety vectors and activation thresholds.
    """
    return api_response({
        "layer": "QERRA-HSR",
        "version": "0.1",
        "description": (
            "Physical safety companion layer to SEMEV-12. "
            "Pure Python, zero ML, deterministic threshold logic."
        ),
        "vectors": {
            "HSR-V01": {
                "name": "immediate_physical_distress",
                "trigger": (
                    "distress_confidence >= 0.75 (CRITICAL direct) "
                    "or >= 0.45 with persons_nearby_count <= 1 "
                    "(CRITICAL combined)"
                )
            },
            "HSR-V02": {
                "name": "human_isolation",
                "trigger": (
                    "persons_nearby_count <= 1 "
                    "with active distress signal"
                )
            },
            "HSR-V03": {
                "name": "environmental_hazard_proximity",
                "trigger": (
                    "hazard_proximity_flag = True "
                    "(CRITICAL, independent of distress signal)"
                )
            }
        },
        "output_states": ["CLEAR", "MONITOR", "CRITICAL"],
        "overhead": "< 1ms per call",
        "interaction_rule": (
            "QERRA-HSR runs before SEMEV-12. "
            "CRITICAL suspends SEMEV-12. "
            "SEMEV-12 BLOCK is never overridden by QERRA-HSR CRITICAL. "
            "suspended_instruction logged on every CRITICAL for "
            "mandatory human review."
        )
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
