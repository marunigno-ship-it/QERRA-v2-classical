# =====================================================
# CLASSICAL ANALYZE ENDPOINT
# High-Quality Entry Point
# =====================================================

from ethical_core import evaluate_ethical_risk


def analyze_text(text: str) -> dict:
    """
    Main entry point for the classical ethical analysis.
    Uses the high-quality ethical core.
    """
    result = evaluate_ethical_risk(text)

    # Add useful metadata (do NOT overwrite version)
    result["framework"] = "QERRA-v2 Classical Edition"

    return result
