"""
QERRA third layer package.

Exposes the ranking functions from thrive_vectors.py so they can be
imported directly from this package — matching how hsr/ is
structured (multiple files, one __init__.py exposing them).

Status: draft. Not calibrated. Not wired into app.py.
"""

from .thrive_vectors import (
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
