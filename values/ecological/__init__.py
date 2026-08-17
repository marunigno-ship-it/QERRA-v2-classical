"""
Suite B: Ecological & Sustainable Companion Suite
Exposes Suite B ranking functions.
"""

from .ecological_vectors import (
    rank_flora_boundary_protection,
    rank_animal_startle_avoidance,
)

ECOLOGICAL_VECTORS = [
    "flora_boundary_protection",
    "animal_startle_avoidance",
]

__all__ = [
    "rank_flora_boundary_protection",
    "rank_animal_startle_avoidance",
    "ECOLOGICAL_VECTORS",
]
