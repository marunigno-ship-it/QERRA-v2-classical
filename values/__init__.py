"""
QERRA Third Layer Package (QERRA-THRIVE).

Exposes Suite A (Human-Centered) and Suite B (Ecological) ranking functions.
Maintains 100% backward compatibility for top-level imports.
"""

from .human_centered import (
    rank_transparent_disclosure,
    rank_balanced_pacing,
    rank_stated_preference_respect,
    rank_sovereign_independence,
    rank_constructive_empathy,
    rank_unbiased_perception,
    rank_spatial_discretion,
    rank_observational_consent,
    rank_proactive_clarity,
    HUMAN_CENTERED_VECTORS,
)

from .ecological import (
    rank_flora_boundary_protection,
    ECOLOGICAL_VECTORS,
)

ALL_THRIVE_VECTORS = HUMAN_CENTERED_VECTORS + ECOLOGICAL_VECTORS

__all__ = [
    # Suite A
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
    # Suite B
    "rank_flora_boundary_protection",
    "ECOLOGICAL_VECTORS",
    # Combined
    "ALL_THRIVE_VECTORS",
]
