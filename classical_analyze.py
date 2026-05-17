# =====================================================
# CLASSICAL ANALYZE ENDPOINT
# High-Quality Entry Point
# Place this file at repo ROOT (same level as app.py and ethical_core.py)
# =====================================================

from ethical_core import evaluate_ethical_risk


def analyze_text(text: str) -> dict:
    """
    Main entry point for the classical ethical analysis.
    Calls evaluate_ethical_risk() from ethical_core.py and adds
    framework metadata without overwriting the version string.
    """
    result = evaluate_ethical_risk(text)

    # Add framework label — do NOT overwrite 'version' from ethical_core
    result["framework"] = "QERRA-v2 Classical Edition"

    return result
