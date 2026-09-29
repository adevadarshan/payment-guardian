# tests/test_rate_limit.py — Slice 4 increment 2: sliding windows + 429 contract.
import pytest

from app.security import ratelimit
from tests.conftest import client, payment_payload


@pytest.fixture(autouse=True)
def _clean_windows():
    ratelimit.reset()
    yield
    ratelimit.reset()


def test_window_allows_then_blocks_then_slides():
    now = [1000.0]
    ratelimit.set_clock(lambda: now[0])
    try:
        for _ in range(3):
            allowed, _ = ratelimit.check("k", 3, window_s=60)
            assert allowed
        allowed, retry = ratelimit.check("k", 3, window_s=60)
        assert not allowed and retry == pytest.approx(60.0)
        now[0] += 61
        allowed, _ = ratelimit.check("k", 3, window_s=60)
        assert allowed
    finally:
        ratelimit.set_clock(__import__("time").time)


def test_analyze_burst_returns_429_with_retry_after(monkeypatch):
    import app.api.deps as deps
    monkeypatch.setattr(deps.settings, "RATE_LIMIT_ANALYZE_IP", 2)
    ratelimit.reset()
    assert client.post("/api/analyze", json=payment_payload()).status_code == 200
    assert client.post("/api/analyze", json=payment_payload()).status_code == 200
    r = client.post("/api/analyze", json=payment_payload())
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited"
    assert r.json()["error"]["details"]["retry_after"] >= 1
    assert "Retry-After" in r.headers


def test_buckets_are_independent_per_key():
    assert ratelimit.check("a", 1)[0] is True
    assert ratelimit.check("a", 1)[0] is False
    assert ratelimit.check("b", 1)[0] is True
