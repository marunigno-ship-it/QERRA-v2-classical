# =====================================================
# models/input.py
# Pydantic input model for clean validation
# =====================================================

from pydantic import BaseModel, Field, field_validator
from typing import Optional

class AnalyzeRequest(BaseModel):
    """Input model for SEMEV-12 ethical analysis."""
    
    text: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="The situation to evaluate (10–5000 characters)"
    )

    @field_validator("text")
    @classmethod
    def text_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError("Text cannot be empty or only whitespace")
        return v.strip()
