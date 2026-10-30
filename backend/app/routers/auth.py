"""
POST /api/auth/login — JWT authentication.

Accepts username/password, verifies against the users table, and returns a
short-lived JWT (HMAC-SHA256, 1 hour).

Also exports the `get_current_user` and `require_role` dependencies used by
protected endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import create_access_token, decode_access_token, verify_password

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


class CurrentUser(BaseModel):
    id: int
    username: str
    role: str


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------

@router.post("/api/auth/login", response_model=LoginOut)
def login(body: LoginIn, db: Session = Depends(get_db)) -> LoginOut:
    user = db.execute(
        select(User).where(User.username == body.username)
    ).scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token(user.id, user.role)
    return LoginOut(access_token=token, role=user.role)


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
        )

    payload = decode_access_token(creds.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
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


def require_role(required_role: str):
    """Return a dependency that ensures the current user has *required_role*.

    Usage:
        @router.post(...)
        def endpoint(user: CurrentUser = Depends(require_role("owner"))):
            ...
    """
    def _role_checker(
        creds: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
        db: Session = Depends(get_db),
    ) -> CurrentUser:
        user = _user_from_token(creds, db)
        if user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required",
            )
        return user

    return _role_checker