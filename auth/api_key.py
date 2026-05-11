# =====================================================
# auth/api_key.py
# Simple API key protection for commercial use
# =====================================================

import os
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

API_KEY_NAME = "x-api-key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def require_api_key(api_key: str = Security(api_key_header)):
    """Require valid API key for protected endpoints."""
    expected_key = os.getenv("QERRA_API_KEY")
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server API key not configured. Contact administrator."
        )
    if api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Contact marunigno@qerra.ai for access."
        )
    return api_key
