# =====================================================
# utils/response.py
# Clean, professional response envelope for QERRA-v2 Classical
# Version: 2.0.0
# =====================================================

from datetime import datetime, timezone

# Single source of truth for QERRA-v2 Classical version
PROJECT_VERSION = "2.0.0"


def api_response(data: dict, status: str = "ok") -> dict:
    """
    Wraps every API response with consistent metadata envelope.
    Ensures all endpoints return auditable versioning and UTC timestamps.
    """
    return {
        "status": status,
        "version": PROJECT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data
    }
