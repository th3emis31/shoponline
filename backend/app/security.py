import hmac

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .config import settings
from .db import get_session
from .services.auth import Principal, any_active_owner, any_users, principal_for_token


def shared_token_allowed(db: Session) -> bool:
    """The shared ADMIN_TOKEN is a setup/emergency key: it works only until a personal
    owner account exists (or always, if ADMIN_TOKEN_ALWAYS=true)."""
    return bool(settings.admin_token) and (settings.admin_token_always or not any_active_owner(db))


def require_admin(x_admin_token: str = Header(default=""), db: Session = Depends(get_session)) -> Principal:
    """Accepts a personal admin session token, or the shared ADMIN_TOKEN (see shared_token_allowed)."""
    if x_admin_token and settings.admin_token and hmac.compare_digest(
        x_admin_token.encode(), settings.admin_token.encode()
    ) and shared_token_allowed(db):
        return Principal(actor="admin-token", role="owner")
    principal = principal_for_token(db, x_admin_token)
    if principal:
        return principal
    # Fail closed: with no token configured and no admin accounts, admin is disabled.
    if not settings.admin_token and not any_users(db):
        raise HTTPException(503, "Admin access is not configured")
    raise HTTPException(401, "Invalid admin token")


def require_owner(principal: Principal = Depends(require_admin)) -> Principal:
    if principal.role != "owner":
        raise HTTPException(403, "Owner access required")
    return principal
