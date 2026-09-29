"""Admin accounts: password hashing, sign-in with lockout, and sessions.

Passwords use scrypt from the Python standard library (no extra dependency).
Session tokens are random; only their SHA-256 hash is stored, so a leaked
database does not leak usable sessions.
"""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import AdminSession, AdminUser

ROLES = ("owner", "staff")
MIN_PASSWORD_LENGTH = 12
MAX_FAILED_ATTEMPTS = 5
LOCKOUT = timedelta(minutes=15)
SESSION_LIFETIME = timedelta(hours=8)
_SCRYPT = {"n": 2**14, "r": 8, "p": 1}


@dataclass(frozen=True)
class Principal:
    actor: str  # email, or "admin-token"
    role: str   # owner | staff


class AuthError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    # SQLite returns naive datetimes; treat stored values as UTC.
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def hash_password(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AuthError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **_SCRYPT)
    return f"scrypt${_SCRYPT['n']}${_SCRYPT['r']}${_SCRYPT['p']}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_hex, digest_hex = stored.split("$")
        if algo != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), dklen=32,
                                n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


# A real hash, used so an unknown email costs the same time as a wrong password.
_DUMMY_HASH = hash_password("x" * MIN_PASSWORD_LENGTH)


def normalise_email(email: str) -> str:
    return email.strip().lower()


def create_user(db: Session, email: str, password: str, role: str) -> AdminUser:
    email = normalise_email(email)
    if role not in ROLES:
        raise AuthError(f"Role must be one of: {', '.join(ROLES)}")
    if "@" not in email:
        raise AuthError("Enter a valid email address")
    if db.scalar(select(AdminUser).where(AdminUser.email == email)):
        raise AuthError("An admin with that email already exists")
    user = AdminUser(email=email, password_hash=hash_password(password), role=role)
    db.add(user)
    db.commit()
    return user


def set_password(db: Session, email: str, password: str) -> None:
    user = db.scalar(select(AdminUser).where(AdminUser.email == normalise_email(email)))
    if user is None:
        raise AuthError("No admin with that email")
    user.password_hash = hash_password(password)
    user.failed_attempts = 0
    user.locked_until = None
    db.execute(delete(AdminSession).where(AdminSession.user_id == user.id))  # sign out everywhere
    db.commit()


def set_active(db: Session, email: str, active: bool) -> None:
    user = db.scalar(select(AdminUser).where(AdminUser.email == normalise_email(email)))
    if user is None:
        raise AuthError("No admin with that email")
    user.active = active
    if not active:
        db.execute(delete(AdminSession).where(AdminSession.user_id == user.id))
    db.commit()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def login(db: Session, email: str, password: str) -> tuple[str, AdminUser, datetime]:
    """Returns (token, user, expires_at). Raises AuthError with a generic message."""
    generic = AuthError("Invalid email or password")
    user = db.scalar(select(AdminUser).where(AdminUser.email == normalise_email(email)))
    if user is None or not user.active:
        verify_password(password, _DUMMY_HASH)
        raise generic
    now = _now()
    locked_until = _aware(user.locked_until)
    if locked_until and locked_until > now:
        raise AuthError("Too many failed attempts. Try again in 15 minutes.")
    if not verify_password(password, user.password_hash):
        user.failed_attempts += 1
        if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = now + LOCKOUT
            user.failed_attempts = 0
        db.commit()
        raise generic
    user.failed_attempts = 0
    user.locked_until = None
    token = secrets.token_urlsafe(32)
    expires = now + SESSION_LIFETIME
    db.add(AdminSession(token_hash=_token_hash(token), user_id=user.id, expires_at=expires))
    # Housekeeping: drop this user's expired sessions.
    db.execute(delete(AdminSession).where(AdminSession.user_id == user.id, AdminSession.expires_at < now))
    db.commit()
    return token, user, expires


def principal_for_token(db: Session, token: str) -> Principal | None:
    if not token:
        return None
    session = db.get(AdminSession, _token_hash(token))
    if session is None or _aware(session.expires_at) <= _now() or not session.user.active:
        return None
    return Principal(actor=session.user.email, role=session.user.role)


def logout(db: Session, token: str) -> None:
    db.execute(delete(AdminSession).where(AdminSession.token_hash == _token_hash(token)))
    db.commit()


def any_users(db: Session) -> bool:
    return db.scalar(select(AdminUser.id).limit(1)) is not None
