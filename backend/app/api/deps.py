# app/api/deps.py — shared FastAPI dependencies (Slice 4).
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import User
from app.db.session import get_db
from app.security import auth as auth_service
from app.security import ratelimit


class RateLimitExceeded(Exception):
    def __init__(self, retry_after: float):
        super().__init__("Rate limit exceeded")
        self.retry_after = retry_after


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def limit_analyze(request: Request) -> None:
    """Rate gate for POST /api/analyze. Raises RateLimitExceeded on breach.

    Per-IP bucket always applies; the per-user bucket activates once
    authentication lands (increment 3) via request.state.user_id.
    """
    user_id = getattr(request.state, "user_id", None)
    if user_id is not None:
        ok, retry = ratelimit.check(
            f"analyze:user:{user_id}", settings.RATE_LIMIT_ANALYZE_USER)
        if not ok:
            raise RateLimitExceeded(retry)
    ok, retry = ratelimit.check(
        f"analyze:ip:{_client_ip(request)}", settings.RATE_LIMIT_ANALYZE_IP)
    if not ok:
        raise RateLimitExceeded(retry)


async def scoped_user_id(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(auth_service.get_current_user),
) -> str | None:
    """User id to scope reads/writes, or None for the flag-off demo path.

    When AUTH_REQUIRED is on, every row is attributed and filtered by caller.
    When off, a single shared demo user acts and all rows (including pre-auth
    NULL rows) stay visible — pre-auth history is never hidden from the demo.
    """
    request.state.user_id = user.id  # feeds the per-user rate bucket
    if not settings.AUTH_REQUIRED:
        return None
    return user.id
