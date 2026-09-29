# tests/test_postgres_parity.py — Slice 4 increment 6: PG behavioral parity.
# Skipped unless TEST_POSTGRES_URL is set (e.g. docker compose service).
# A skip is recorded as environment-blocked verification, not a pass.
import os

import pytest

REQUIRED = os.environ.get("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not REQUIRED, reason="TEST_POSTGRES_URL unset")


@pytest.fixture()
def pg_client(monkeypatch):
    import sys
    for module in [m for m in list(sys.modules) if m.startswith(("app.", "tests."))]:
        del sys.modules[module]
    monkeypatch.setenv("DATABASE_URL", REQUIRED)
    monkeypatch.setenv("AUTH_REQUIRED", "false")
    monkeypatch.setenv("RATE_LIMIT_ANALYZE_IP", "10000")
    monkeypatch.setenv("ALLOW_CLIENT_HOUR", "true")
    import subprocess
    subprocess.run(["alembic", "upgrade", "head"], check=True,
                   cwd=os.path.join(os.path.dirname(__file__), ".."))
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as test_client:
        yield test_client


def _payment(**overrides):
    base = {"amount": 3500.0, "currency": "INR", "payee_id": "vendor@upi",
            "payee_name": "Vendor", "sender_balance": 20000.0, "note": "headphones",
            "channel": "upi", "merchant_category": "Electronics"}
    base.update(overrides)
    return {"analysis_type": "payment", "payment": base}


def test_pg_golden_payment_case(pg_client):
    body = dict(_payment())
    body["timestamp"] = "2026-09-29T14:00:00+00:00"
    data = pg_client.post("/api/analyze", json=body).json()
    assert (data["risk_score"], data["risk_level"]) == (35, "MEDIUM")


def test_pg_chain_tamper_and_seen(pg_client):
    first = pg_client.post("/api/analyze", json={
        "analysis_type": "qr",
        "qr": {"payload": "upi://pay?pa=pgparity@upi&pn=PG&am=10"}}).json()
    assert first["seen"]["status"] == "new"
    second = pg_client.post("/api/analyze", json={
        "analysis_type": "qr",
        "qr": {"payload": "upi://pay?pa=pgparity@upi&pn=PG&am=10"}}).json()
    assert second["seen"]["status"] == "previously_seen"
    assert second["seen"]["times_seen"] == 2
    assert pg_client.post("/api/audit/verify", json={}).json()["valid"] is True


def test_pg_old_row_shape(pg_client):
    stats = pg_client.get("/api/stats").json()
    assert set(stats) == {"total", "safe", "medium", "high", "fraud_rate"}
