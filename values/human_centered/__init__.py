"""
Suite A: Human-Centered Companion Suite
Exposes Suite A ranking functions.
"""

from .human_vectors import (
    rank_transparent_disclosure,
    rank_balanced_pacing,
    rank_stated_preference_respect,
    rank_sovereign_independence,
    rank_constructive_empathy,
    rank_unbiased_perception,
    rank_spatial_discretion,
    rank_observational_consent,
    rank_proactive_clarity,
)

HUMAN_CENTERED_VECTORS = [
    "transparent_disclosure",
    "balanced_pacing",
    "stated_preference_respect",
    "sovereign_independence",
    "constructive_empathy",
    "unbiased_perception",
    "spatial_discretion",
    "observational_consent",
    "proactive_clarity",
]

__all__ = [
    "rank_transparent_disclosure",
    "rank_balanced_pacing",
    "rank_stated_preference_respect",
    "rank_sovereign_independence",
    "rank_constructive_empathy",
    "rank_unbiased_perception",
    "rank_spatial_discretion",
    "rank_observational_consent",
    "rank_proactive_clarity",
    "HUMAN_CENTERED_VECTORS",
]
