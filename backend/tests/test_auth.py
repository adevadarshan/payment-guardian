# tests/test_auth.py — Slice 4 increment 3: login/refresh/logout/me.
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
    from app.security import ratelimit
    ratelimit.reset()


def _register(db_email, password="secret1234"):
    from app.db.models import User
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == db_email).first()
        if user is None:
            user = User(email=db_email, password_hash=auth_service.hash_password(password),
                        display_name="T", is_demo=False)
            db.add(user)
            db.commit()
    finally:
        db.close()


def _login(email, password="secret1234"):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_login_logout_me_flow(auth_on):
    _register("alice@example.com")
    tokens = _login("alice@example.com").json()
    assert set(tokens) >= {"access_token", "refresh_token", "token_type", "expires_in"}
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200 and me.json()["email"] == "alice@example.com"
    assert client.post("/api/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_bad_password_and_unknown_user_401(auth_on):
    _register("bob@example.com")
    assert _login("bob@example.com", "wrong").status_code == 401
    assert _login("nobody@example.com", "wrong").status_code == 401
    assert client.get("/api/stats").status_code == 401
    assert client.post("/api/analyze", json=payment_payload()).status_code == 401


def test_expired_token_rejected(auth_on, monkeypatch):
    import datetime
    _register("carol@example.com")
    tokens = _login("carol@example.com").json()
    real_now = datetime.datetime.now
    monkeypatch.setattr(auth_service, "_now",
                        lambda: real_now(datetime.timezone.utc) + datetime.timedelta(hours=2))
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_refresh_rotates(auth_on):
    _register("dave@example.com")
    tokens = _login("dave@example.com").json()
    rotated = client.post("/api/auth/refresh",
                          json={"refresh_token": tokens["refresh_token"]}).json()
    assert rotated["access_token"] != tokens["access_token"]
    # Old refresh token is dead after rotation.
    assert client.post("/api/auth/refresh",
                       json={"refresh_token": tokens["refresh_token"]}).status_code == 401
    headers = {"Authorization": f"Bearer {rotated['access_token']}"}
    assert client.get("/api/auth/me", headers=headers).status_code == 200


def test_demo_flag_off_needs_no_login():
    r = client.post("/api/analyze", json=payment_payload())
    assert r.status_code == 200
    assert client.get("/api/stats").status_code == 200
