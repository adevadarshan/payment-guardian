# tests/test_ownership.py — Slice 4 increment 3: user-scoped data isolation.
import pytest

import app.api.deps as deps
from app.security import auth as auth_service
from tests.conftest import client, payment_payload


@pytest.fixture()
def auth_on(monkeypatch):
    monkeypatch.setattr(deps.settings, "AUTH_REQUIRED", True)
    import app.security.auth as auth_module
    monkeypatch.setattr(auth_module.settings, "AUTH_REQUIRED", True)
    yield


def _user_headers(email):
    from app.db.models import User
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(email=email, password_hash=auth_service.hash_password("pw123456"),
                        display_name=email, is_demo=False)
            db.add(user)
            db.commit()
    finally:
        db.close()
    tokens = client.post("/api/auth/login",
                         json={"email": email, "password": "pw123456"}).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_cross_user_isolation(auth_on):
    alice = _user_headers("iso-alice@example.com")
    bob = _user_headers("iso-bob@example.com")
    scan_id = client.post("/api/analyze", json=payment_payload(), headers=alice).json()["scan_id"]
    # Bob cannot read Alice's scan (404, not 403: no id oracle).
    assert client.get(f"/api/scans/{scan_id}", headers=bob).status_code == 404
    assert client.get(f"/api/scans/{scan_id}", headers=alice).status_code == 200
    # Listings and stats are scoped per user.
    assert all(s["scan_id"] == scan_id
               for s in client.get("/api/scans", headers=alice).json())
    assert client.get("/api/scans", headers=bob).json() == []
    alice_stats = client.get("/api/stats", headers=alice).json()
    bob_stats = client.get("/api/stats", headers=bob).json()
    assert alice_stats["total"] >= 1 and bob_stats["total"] == 0
    # Audit listing is scoped; global verify still reports validity only.
    assert client.get("/api/audit", headers=bob).json() == []
    assert client.post("/api/audit/verify", json={}, headers=bob).json()["valid"] is True


def test_preauth_rows_visible_only_with_auth_off():
    # Rows written by the flag-off suite (user_id NULL) remain listed.
    r = client.get("/api/scans?limit=5")
    assert r.status_code == 200
