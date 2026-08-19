"""
Suite B: Ecological & Sustainable Companion Suite
Exposes Suite B ranking functions.
"""

from .ecological_vectors import (
    rank_flora_boundary_protection,
    rank_animal_startle_avoidance,
    rank_minimal_disturbance_footprint,
)

ECOLOGICAL_VECTORS = [
    "flora_boundary_protection",
    "animal_startle_avoidance",
    "minimal_disturbance_footprint",
]

__all__ = [
    "rank_flora_boundary_protection",
    "rank_animal_startle_avoidance",
    "rank_minimal_disturbance_footprint",
    "ECOLOGICAL_VECTORS",
]
