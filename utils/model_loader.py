"""
utils/model_loader.py
QERRA-v2 Classical — Shared Model Singleton Provider

Ensures exactly ONE instance of SentenceTransformer('all-MiniLM-L6-v2') is loaded
into memory across all three layers (SEMEV-12, QERRA-HSR, QERRA-THRIVE), keeping
the total RAM footprint at a flat ~250MB and eliminating memory triplication.
"""

import logging
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Global singleton reference
_shared_model = None


def get_shared_model(model_name: str = 'all-MiniLM-L6-v2') -> SentenceTransformer:
    """
    Returns the shared SentenceTransformer singleton instance.
    Loads the model weights into RAM once on first invocation.
    Subsequent calls from any layer or module reuse the existing in-memory instance.
    """
    global _shared_model
    if _shared_model is None:
        logger.info(f"Initializing shared SentenceTransformer singleton: '{model_name}'...")
        _shared_model = SentenceTransformer(model_name)
        logger.info(f"Shared model '{model_name}' successfully loaded into RAM.")
    return _shared_model


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Shared Model Singleton...")
    m1 = get_shared_model()
    m2 = get_shared_model()
    # Memory identity verification (both variables point to exact same memory address)
    is_same_instance = (m1 is m2)
    print(f"Model 1 Memory ID : {id(m1)}")
    print(f"Model 2 Memory ID : {id(m2)}")
    print(f"Single RAM Instance Verified: {is_same_instance}")
    print("=" * 60)
