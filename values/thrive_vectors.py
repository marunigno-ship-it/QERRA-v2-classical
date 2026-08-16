"""
QERRA Third Layer Package — Backward Compatibility Bridge.

Re-exports Suite A ranking functions from values.human_centered.human_vectors
to ensure legacy callers and tests importing directly from thrive_vectors.py
continue working with zero breaking changes.
"""

from .human_centered.human_vectors import (
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
]
