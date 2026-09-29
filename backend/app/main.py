# app/main.py — FastAPI application (Slice 4, clean-room).
# Run from backend/: uvicorn app.main:app --reload

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import analyze, audit, auth, health, scans, stats
from app.api.deps import RateLimitExceeded
from app.config import settings, validate_production
from app.logging_redact import install as install_redaction


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response


class ContentLengthGuardMiddleware(BaseHTTPMiddleware):
    """Reject oversized request bodies on /api/* before Pydantic parsing."""

    def __init__(self, app, max_bytes: int):
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/"):
            try:
                length = int(request.headers.get("content-length", "0") or "0")
            except ValueError:
                length = 0
            if length > self.max_bytes:
                return JSONResponse(
                    status_code=413,
                    content={"error": {
                        "code": "too_large",
                        "message": "Request body exceeds the size limit.",
                    }},
                )
        return await call_next(request)


@asynccontextmanager
async def lifespan(_: FastAPI):
    install_redaction()
    problems = validate_production(settings)
    if problems:
        raise RuntimeError("Refusing to start with unsafe production config: "
                           + "; ".join(problems))
    from app.ml import registry as ml_registry
    ml_registry.preload(settings.MODEL_BACKEND)
    print(f"[VH-S02] starting (env={settings.APP_ENV}, pipeline={settings.PIPELINE_VERSION})")
    yield


app = FastAPI(title="VH-S02 API", version="0.1.0-slice-4", lifespan=lifespan)

if settings.APP_ENV == "production":
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_host_list)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(ContentLengthGuardMiddleware, max_bytes=settings.MAX_CONTENT_BYTES)


@app.exception_handler(RequestValidationError)
async def validation_envelope(_: Request, exc: RequestValidationError):
    # Stable error envelope the web client switches on.
    # Pydantic error dicts can carry non-serializable ctx values — stringify them.
    details = []
    for err in exc.errors():
        err = dict(err)
        if isinstance(err.get("ctx"), dict):
            err["ctx"] = {k: str(v) for k, v in err["ctx"].items()}
        err.pop("url", None)
        details.append(err)
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request failed validation.",
                "details": details,
            }
        },
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_envelope(_: Request, exc: RateLimitExceeded):
    retry = max(1, int(exc.retry_after + 0.999))
    return JSONResponse(
        status_code=429,
        headers={"Retry-After": str(retry)},
        content={"error": {
            "code": "rate_limited",
            "message": f"Rate limit exceeded. Retry in {retry}s.",
            "details": {"retry_after": retry},
        }},
    )


@app.exception_handler(Exception)
async def server_envelope(request: Request, exc: Exception):
    # Never leak tracebacks to clients. Server-side logging goes through the
    # redacted handler chain (installed at startup); clients get a generic code.
    import logging
    from fastapi import HTTPException

    if isinstance(exc, HTTPException):
        raise exc
    logging.getLogger("vh-s02").exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "server_error", "message": "Unexpected server error."}},
    )


app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(analyze.router, prefix="/api", tags=["analyze"])
app.include_router(scans.router, prefix="/api", tags=["scans"])
app.include_router(stats.router, prefix="/api", tags=["stats"])
app.include_router(audit.router, prefix="/api", tags=["audit"])
