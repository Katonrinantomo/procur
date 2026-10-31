"""
POST /api/auth/login — JWT authentication.

Accepts username/password, verifies against the users table, and returns a
short-lived JWT (HMAC-SHA256, 1 hour).

Also exports `get_current_user`, `require_roles`, and `require_role`
dependencies used by protected endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import create_access_token, decode_access_token, limiter, verify_password

router = APIRouter()

_bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LoginIn(BaseModel):
    username: str
    password: str


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


class CurrentUser(BaseModel):
    id: int
    username: str
    role: str


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------

@router.post("/api/auth/login", response_model=LoginOut)
@limiter.limit("5/minute")
def login(request: Request, body: LoginIn, db: Session = Depends(get_db)) -> LoginOut:
    user = db.execute(
        select(User).where(User.username == body.username)
    ).scalar_one_or_none()

    if user is None or not user.is_active or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token(user.id, user.role)
    return LoginOut(access_token=token, role=user.role, username=user.username)


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def _user_from_token(
    creds: HTTPAuthorizationCredentials | None,
    db: Session,
) -> CurrentUser:
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(creds.credentials)
    if payload is None or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return CurrentUser(id=user.id, username=user.username, role=user.role)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """Extract the JWT from the Authorization header and return the user.

    Raises 401 on any failure (missing header, invalid token, unknown user).
    """
    return _user_from_token(creds, db)


def require_roles(*roles: str):
    """Return a dependency that ensures the current user has one of *roles*.

    Usage:
        @router.post(...)
        def endpoint(user: CurrentUser = Depends(require_roles("owner", "finance"))):
            ...
    """
    role_set = frozenset(roles)

    def _checker(
        creds: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
        db: Session = Depends(get_db),
    ) -> CurrentUser:
        user = _user_from_token(creds, db)
        if user.role not in role_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"One of roles {sorted(role_set)} required",
            )
        return user

    return _checker


def require_role(required_role: str):
    """Return a dependency that ensures the current user has *required_role*.

    Kept for backward compatibility; prefer require_roles(*roles) for new code.
    """
    return require_roles(required_role)
