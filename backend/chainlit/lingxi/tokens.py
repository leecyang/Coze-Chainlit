"""Service Identity Token validation helpers."""

from datetime import datetime
from typing import Any, Dict, Optional


TOKEN_EXPIRY_BUFFER_SECONDS = 3600


def get_service_token_status(token: Optional[str], expires_at: Optional[str]) -> Dict[str, Any]:
    """Return availability, validity, and expiry diagnostics for the service token."""
    status = {"available": False, "valid": False, "expires_in": None}
    if not token:
        return status

    status["available"] = True
    if not expires_at:
        status["valid"] = True
        return status

    try:
        expires_in = int(expires_at) - int(datetime.now().timestamp())
    except (ValueError, TypeError):
        return status

    status["expires_in"] = expires_in
    status["valid"] = expires_in > TOKEN_EXPIRY_BUFFER_SECONDS
    return status


def build_token_health(token: Optional[str], expires_at: Optional[str]) -> Dict[str, Any]:
    """Build the admin-facing token health payload."""
    service_status = get_service_token_status(token, expires_at)
    recommendation = (
        "✅ Service Identity token active - production ready"
        if service_status["valid"]
        else "❌ No valid token configured!"
    )
    return {
        "service_identity": service_status,
        "recommendation": recommendation,
    }
