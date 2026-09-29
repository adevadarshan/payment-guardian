# app/security/auth.py — opaque bearer sessions, Argon2id passwords (Slice 4).
# No custom pepper (not required): Argon2id via argon2-cffi directly.
# Tokens are random, SHA-256 hashed at rest, expiring, revocable.
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Session as SessionRow
from app.db.models import User
from app.db.session import get_db

_ph = PasswordHasher()

ACCESS_MINUTES = 60
REFRESH_DAYS = 7


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def _mint(user_id: str, kind: str, lifetime: timedelta) -> tuple[str, SessionRow]:
    token = secrets.token_urlsafe(32)
    row = SessionRow(
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        user_id=user_id,
        kind=kind,
        expires_at=datetime.now(timezone.utc) + lifetime,
    )
    return token, row


def issue_pair(db: Session, user: User) -> dict:
    access, access_row = _mint(user.id, "access", timedelta(minutes=ACCESS_MINUTES))
    refresh, refresh_row = _mint(user.id, "refresh", timedelta(days=REFRESH_DAYS))
    db.add(access_row)
    db.add(refresh_row)
    db.commit()
    return {"access_token": access, "refresh_token": refresh,
            "token_type": "bearer", "expires_in": ACCESS_MINUTES * 60}


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(moment: datetime) -> datetime:
    # SQLite returns naive datetimes; Postgres returns aware ones.
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


def user_for_token(db: Session, token: str, *, kind: str = "access") -> User | None:
    digest = hashlib.sha256(token.encode()).hexdigest()
    row = db.query(SessionRow).filter(
        SessionRow.token_hash == digest, SessionRow.kind == kind).first()
    if row is None or _as_utc(row.expires_at) <= _now():
        return None
    return db.query(User).filter(User.id == row.user_id).first()


def revoke_token(db: Session, token: str) -> None:
    digest = hashlib.sha256(token.encode()).hexdigest()
    db.query(SessionRow).filter(SessionRow.token_hash == digest).delete()
    db.commit()


def ensure_demo_user(db: Session) -> User:
    """Get-or-create the env-seeded demo user (flag-off path + seeding)."""
    user = db.query(User).filter(User.email == settings.DEMO_EMAIL).first()
    if user is None:
        user = User(email=settings.DEMO_EMAIL,
                    password_hash=hash_password(settings.DEMO_PASSWORD),
                    display_name="Demo", is_demo=True)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Auth dependency. When AUTH_REQUIRED=false, runs as the demo user."""
    if not settings.AUTH_REQUIRED:
        return ensure_demo_user(db)
    token = _bearer_token(request)
    if token is None:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    user = user_for_token(db, token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    request.state.user_id = user.id
    return user
