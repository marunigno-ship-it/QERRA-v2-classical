# =====================================================
# CLASSICAL ANALYZE ENDPOINT
# High-Quality Entry Point (Single & Batch Support)
# Place this file at repo ROOT (same level as app.py and ethical_core.py)
# =====================================================

from typing import List, Dict, Any
from ethical_core import evaluate_ethical_risk, evaluate_ethical_risk_batch


def analyze_text(text: str) -> dict:
    """
    Main entry point for classical single-text ethical analysis.
    Calls evaluate_ethical_risk() from ethical_core.py and adds
    framework metadata without overwriting the version string.
    """
    result = evaluate_ethical_risk(text)

    # Add framework label — do NOT overwrite 'version' from ethical_core
    result["framework"] = "QERRA-v2 Classical Edition"

    return result


def analyze_text_batch(texts: List[str]) -> List[dict]:
    """
    High-performance batch entry point for evaluating multiple candidate actions.
    Encodes all candidate actions in a single neural pass to preserve ROS 2 real-time margins.
    """
    results = evaluate_ethical_risk_batch(texts)

    for res in results:
        res["framework"] = "QERRA-v2 Classical Edition"

    return results
