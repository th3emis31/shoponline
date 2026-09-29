import hmac

from fastapi import Header, HTTPException

from .config import settings


def require_admin(x_admin_token: str = Header(default="")):
    # Fail closed: admin endpoints are disabled unless a token is configured.
    if not settings.admin_token:
        raise HTTPException(503, "Admin access is not configured")
    if not hmac.compare_digest(x_admin_token.encode(), settings.admin_token.encode()):
        raise HTTPException(401, "Invalid admin token")
