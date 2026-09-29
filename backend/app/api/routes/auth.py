# app/api/routes/auth.py — login/refresh/logout/me (Slice 4).
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import RateLimitExceeded
from app.config import settings
from app.db.models import User
from app.db.session import get_db
from app.security import auth as auth_service
from app.security import ratelimit

router = APIRouter()


class LoginIn(BaseModel):
    model_config = {"extra": "forbid"}
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=1, max_length=256)


class RefreshIn(BaseModel):
    model_config = {"extra": "forbid"}
    refresh_token: str = Field(..., min_length=1)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class MeOut(BaseModel):
    id: str
    email: str
    display_name: str | None = None
    is_demo: bool = False


def _login_allowed(request: Request) -> None:
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
        request.client.host if request.client else "unknown")
    ok, retry = ratelimit.check(f"login:ip:{ip}", settings.RATE_LIMIT_LOGIN_IP)
    if not ok:
        raise RateLimitExceeded(retry)


@router.post("/auth/login", response_model=TokenPair)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    _login_allowed(request)
    user = db.query(User).filter(User.email == body.email.strip().lower()).first()
    # Identical timing shape for unknown emails: always run one verification.
    candidate = user.password_hash if user else auth_service.hash_password("dummy-seed-value")
    valid = auth_service.verify_password(candidate, body.password) and user is not None
    if not valid:
        # Constant-time-ish failure path; no user enumeration via message.
        raise HTTPException(status_code=401, detail="Invalid email or password")
    assert user is not None
    return auth_service.issue_pair(db, user)


@router.post("/auth/refresh", response_model=TokenPair)
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    user = auth_service.user_for_token(db, body.refresh_token, kind="refresh")
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    auth_service.revoke_token(db, body.refresh_token)  # rotation: old refresh dies
    return auth_service.issue_pair(db, user)


@router.post("/auth/logout")
def logout(request: Request, db: Session = Depends(get_db),
           user: User = Depends(auth_service.get_current_user)):
    header = request.headers.get("authorization", "")
    _, _, token = header.partition(" ")
    if token.strip():
        auth_service.revoke_token(db, token.strip())
    return {"status": "ok"}


@router.get("/auth/me", response_model=MeOut)
def me(user: User = Depends(auth_service.get_current_user)):
    return MeOut(id=user.id, email=user.email,
                 display_name=user.display_name, is_demo=user.is_demo)
