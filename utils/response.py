# =====================================================
# utils/response.py
# Clean, professional response envelope for QERRA-v2 Classical
# =====================================================

from datetime import datetime, timezone

# Single source of truth for version
PROJECT_VERSION = "1.7-classical-nuance-calibrated"

def api_response(data: dict, status: str = "ok") -> dict:
    """
    Wraps every API response with consistent metadata.
    Makes the API look professional and commercial-ready.
    """
    return {
        "status": status,
        "version": PROJECT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data
    }
