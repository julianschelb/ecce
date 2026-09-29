"""Admin authentication: password login, signed bearer tokens, guard dependency."""

from __future__ import annotations

import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings

ALGORITHM = "HS256"
_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AdminPrincipal:
    """Identity attached to authenticated admin requests."""

    subject: str
    role: str = "admin"


def verify_admin_password(settings: Settings, password: str) -> bool:
    """Constant-time comparison against ``ADMIN_PASSWORD``."""
    if not settings.admin_password:
        return False
    return secrets.compare_digest(password.encode("utf-8"), settings.admin_password.encode("utf-8"))


def create_access_token(settings: Settings, subject: str = "admin") -> tuple[str, int]:
    """Return a signed JWT and its lifetime in seconds."""
    ttl = timedelta(minutes=settings.token_ttl_minutes)
    now = datetime.now(UTC)
    payload = {"sub": subject, "role": "admin", "iat": now, "exp": now + ttl}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM), int(ttl.total_seconds())


def decode_access_token(settings: Settings, token: str) -> AdminPrincipal:
    """Validate a token; raises ``HTTPException(401)`` when invalid or expired."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired") from error
    except jwt.PyJWTError as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from error
    if payload.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
    return AdminPrincipal(subject=str(payload.get("sub", "admin")))


def settings_dependency(request: Request) -> Settings:
    """Settings of the running app (overridable in tests via ``app.state.settings``)."""
    settings: Settings | None = getattr(request.app.state, "settings", None)
    return settings or get_settings()


def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(settings_dependency),
) -> AdminPrincipal:
    """FastAPI dependency protecting write endpoints."""
    if not settings.admin_enabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Admin access is disabled: set the ADMIN_PASSWORD environment variable",
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Admin token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_access_token(settings, credentials.credentials)


def optional_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(settings_dependency),
) -> AdminPrincipal | None:
    """Like :func:`require_admin` but returns ``None`` for anonymous requests."""
    if credentials is None or not settings.admin_enabled:
        return None
    try:
        return decode_access_token(settings, credentials.credentials)
    except HTTPException:
        return None


class LoginRateLimiter:
    """Small in-memory sliding-window limiter (login and contact form), keyed by IP address."""

    def __init__(
        self,
        attempts_per_minute: int,
        window: float = 60,
        message: str = "Too many login attempts",
    ) -> None:
        self.limit = attempts_per_minute  # attempts per window
        self.window = window
        self.message = message
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            # forget addresses without attempts in the last window (data minimisation)
            for stale in [k for k, w in self._hits.items() if not w or now - w[-1] > self.window]:
                del self._hits[stale]
            window = self._hits[key]
            while window and now - window[0] > self.window:
                window.popleft()
            if len(window) >= self.limit:
                raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, self.message)
            window.append(now)
