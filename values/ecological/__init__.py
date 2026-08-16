"""
Suite B: Ecological & Sustainable Companion Suite
Exposes Suite B ranking functions.
"""

from .ecological_vectors import rank_flora_boundary_protection

ECOLOGICAL_VECTORS = [
    "flora_boundary_protection",
]

__all__ = [
    "rank_flora_boundary_protection",
    "ECOLOGICAL_VECTORS",
]
