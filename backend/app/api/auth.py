"""Admin login."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.config import Settings
from app.core.security import (
    AdminPrincipal,
    LoginRateLimiter,
    create_access_token,
    require_admin,
    settings_dependency,
    verify_admin_password,
)
from app.models.schemas import LoginRequest, Principal, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _limiter(request: Request) -> LoginRateLimiter:
    limiter = getattr(request.app.state, "login_limiter", None)
    if limiter is None:
        limiter = LoginRateLimiter(request.app.state.settings.login_attempts_per_minute)
        request.app.state.login_limiter = limiter
    return limiter


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    request: Request,
    settings: Settings = Depends(settings_dependency),
    limiter: LoginRateLimiter = Depends(_limiter),
) -> TokenResponse:
    """Exchange the admin password for a bearer token."""
    if not settings.admin_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Admin access is disabled")
    limiter.check(request.client.host if request.client else "anonymous")
    if not verify_admin_password(settings, body.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong password")
    token, expires_in = create_access_token(settings)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=Principal)
def me(principal: AdminPrincipal = Depends(require_admin)) -> Principal:
    """Validate the current token."""
    return Principal(subject=principal.subject, role=principal.role)
