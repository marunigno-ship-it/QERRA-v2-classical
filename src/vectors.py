# =====================================================
# SACRED VECTORS - QERRA-v2 Classical Edition
# These vectors are sacred. We only polish, never change the core.
# Now complete SEMEV-12
# =====================================================

VECTORS = {
    "v001": {"name": "coherence_protection", "weight": 1.0, "description": "Protection of mental and emotional coherence"},
    "v002": {"name": "family_severance", "weight": 0.95, "description": "Detection of toxic family or relational severance"},
    "v003": {"name": "survival_instinct", "weight": 1.0, "description": "Human survival and self-protection priority"},
    "v004": {"name": "moral_pressure", "weight": 0.9, "description": "Detection of external moral or financial pressure"},
    "v005": {"name": "harm_intent", "weight": 1.0, "description": "Core harm detection (self or others)"},
    "v006": {"name": "family_origin_chain", "weight": 0.85, "description": "Family-origin ethical chain"},
    "v007": {"name": "personal_potential", "weight": 0.9, "description": "Suppression or support of personal potential"},
    "v008": {"name": "shallow_remorse", "weight": 0.8, "description": "Detection of shallow or manipulative remorse"},
    "v009": {"name": "ethical_severance", "weight": 0.95, "description": "Final ethical severance from toxic patterns"},
    # Added 3 missing vectors to reach SEMEV-12
    "v010": {"name": "cognitive_manipulation", "weight": 0.9, "description": "Detection of gaslighting or cognitive manipulation"},
    "v011": {"name": "autonomy_violation", "weight": 0.95, "description": "Violation of personal autonomy and free will"},
    "v012": {"name": "institutional_trust", "weight": 0.85, "description": "Detection of institutional or systemic betrayal"},
}

def get_sacred_vectors():
    """Return all sacred vectors without modification."""
    return VECTORS.copy()  # safe copy - core remains untouched