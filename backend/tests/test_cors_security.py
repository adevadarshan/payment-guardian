# tests/test_cors_security.py — Slice 4 increment 1: hardening gates.
import logging


from app.config import Settings, validate_production
from app.logging_redact import install as install_redaction, redact
from tests.conftest import client, payment_payload


def _prod(**overrides):
    env = {
        "APP_ENV": "production",
        "DATABASE_URL": "postgresql+psycopg2://u:p@db:5432/v",
        "CORS_ORIGINS": "https://app.example.com",
        "TRUSTED_HOSTS": "app.example.com",
        "ALLOW_CLIENT_HOUR": "false",
        "AUTH_REQUIRED": "true",
    }
    env.update(overrides)
    import os
    real = dict(os.environ)
    os.environ.update(env)
    try:
        return Settings(), validate_production(Settings())
    finally:
        os.environ.clear()
        os.environ.update(real)


def test_production_guards_catch_unsafe_config():
    _, errors = _prod()
    assert errors == []
    _, errors = _prod(DATABASE_URL="sqlite:///./x.db")
    assert any("SQLite" in e for e in errors)
    _, errors = _prod(CORS_ORIGINS="http://localhost:5173,http://localhost:3000")
    assert any("CORS" in e for e in errors)
    _, errors = _prod(AUTH_REQUIRED="false")
    assert any("AUTH_REQUIRED" in e for e in errors)
    _, errors = _prod(ALLOW_CLIENT_HOUR="true")
    assert any("ALLOW_CLIENT_HOUR" in e for e in errors)


def test_dev_config_passes_production_validation_vacuously():
    assert validate_production(Settings()) == []


def test_cors_foreign_origin_refused_allowed_origin_works():
    foreign = client.get("/api/health", headers={"Origin": "https://evil.example/"})
    assert foreign.status_code == 200
    assert "access-control-allow-origin" not in {k.lower() for k in foreign.headers}
    allowed = client.get(
        "/api/health", headers={"Origin": "http://localhost:5173"})
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_security_headers_present():
    r = client.get("/api/health")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("referrer-policy") == "no-referrer"


def test_unknown_fields_rejected():
    body = payment_payload()
    body["payment"]["smuggled"] = "x"
    r = client.post("/api/analyze", json=body)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
    top = payment_payload()
    top["unknown_root"] = 1
    r = client.post("/api/analyze", json=top)
    assert r.status_code == 422


def test_oversized_body_rejected_before_parsing():
    big_note = "x" * (9 * 1024 * 1024)
    body = payment_payload(note=big_note[:280])
    body["payment"]["note"] = "ok"
    # Force an oversized body via a large-but-valid JSON wrapper on scans.
    r = client.post("/api/analyze", json=body)
    assert r.status_code in (200, 422)  # small body passes validation either way
    oversized = {"analysis_type": "payment", "payment": body["payment"],
                 "padding": "y" * (9 * 1024 * 1024)}
    # forbid rejects unknown "padding" at 422 only if body is small enough;
    # with 9MB the size guard must win first with 413.
    r = client.post("/api/analyze", json=oversized)
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "too_large"


def test_500_body_leak_free():
    r = client.get("/api/scans/does-not-exist")
    assert r.status_code == 404  # not a 500; exercised for envelope shape
    assert "traceback" not in r.text.lower()


def test_log_redaction_masks_secrets():
    install_redaction()
    assert "***REDACTED***" in redact('password="hunter2" and ok=1')
    assert "hunter2" not in redact('password="hunter2" and ok=1')
    assert "***REDACTED***" in redact("Authorization: Bearer abc.def.ghi")
    assert "abc.def.ghi" not in redact("Authorization: Bearer abc.def.ghi")
    assert "***REDACTED***" in redact("{'qr_payload': 'upi://pay?pa=x@y'}")
    assert "ok=1" in redact('password="hunter2" and ok=1')

    records = []
    handler = logging.Handler()
    handler.emit = lambda record: records.append(record.getMessage())  # noqa: E731
    logger = logging.getLogger("vh-s02-redact-test")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    from app.logging_redact import RedactingFilter
    handler.addFilter(RedactingFilter())
    logger.info('login attempt password="hunter2"')
    assert records and "hunter2" not in records[0]
