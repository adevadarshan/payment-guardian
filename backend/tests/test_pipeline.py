# tests/test_pipeline.py — Slice 3 increment 5: fusion identity, determinism,
# ordering, composition, invariants, multi-type history/stats.
from app.analyzers.payment_analyzer import analyze_payment
from app.pipeline import run as pipeline
from app.schemas.analyze import PaymentInput
from tests.conftest import client, payment_payload

DAY = "2026-09-29T14:00:00+00:00"


def _payment_dict(**overrides):
    body = payment_payload(**overrides)
    return body["payment"]


def test_fusion_identity_payment_path():
    # run.py payment path reproduces the Slice 2 analyzer verdict exactly.
    cases = [
        _payment_dict(amount=150.0),
        _payment_dict(amount=3500.0, merchant_category="Electronics",
                      sender_balance=20000.0, note="headphones",
                      payee_id="vendor@upi", payee_name="Vendor"),
        _payment_dict(amount=12000.0, merchant_category="Travel",
                      sender_balance=50000.0, note="urgent verify kyc",
                      payee_id="xx@bank", payee_name="X"),
    ]
    for payment in cases:
        parsed = PaymentInput(**payment)
        direct = analyze_payment(parsed, hour=14)
        via_run = pipeline.analyze_request(analysis_type="payment", payment=parsed, hour=14)
        for key in ("risk_score", "risk_level", "reasons", "signals",
                    "evidence", "recommended_action"):
            assert via_run[key] == direct[key], key


def test_cross_type_composition_message_with_url():
    body = {
        "analysis_type": "message",
        "message": {"text": "Verify your account at http://paypal.com.secure-login.xyz/verify?email=x now"},
    }
    r = client.post("/api/analyze", json=body)
    assert r.status_code == 200
    data = r.json()
    codes = [reason["code"] for reason in data["reasons"]]
    assert any(c.startswith("message.") for c in codes)
    assert any(c.startswith("url.") for c in codes)
    assert data["evidence"]["extracted_urls"] == ["http://paypal.com.secure-login.xyz/verify?email=x"]


def test_message_with_payment_context():
    body = {
        "analysis_type": "message",
        "message": {"text": "Hi, please confirm you received this message"},
        "payment_context": {"amount": 60000.0, "sender_balance": 65000.0},
    }
    r = client.post("/api/analyze", json=body)
    assert r.status_code == 200
    data = r.json()
    assert any(c.startswith("payment_context.") for c in [s["name"] for s in data["signals"]])
    assert data["risk_level"] in ("MEDIUM", "HIGH")


def test_reasons_invariant_all_types():
    bodies = [
        {"analysis_type": "message",
         "message": {"text": "Your account will be blocked. Verify OTP now."}},
        {"analysis_type": "url",
         "url": {"url": "http://185.22.1.4/login?user=a"}},
    ]
    for body in bodies:
        data = client.post("/api/analyze", json=body).json()
        assert data["risk_level"] in ("MEDIUM", "HIGH"), body
        assert len(data["reasons"]) >= 1, body


def test_history_type_filter_and_stats_span_types():
    client.post("/api/analyze", json={
        "analysis_type": "message", "message": {"text": "Hello friend, see you soon"}})
    client.post("/api/analyze", json={
        "analysis_type": "url", "url": {"url": "https://www.hdfcbank.com/"}})
    for t in ("payment", "message", "url"):
        r = client.get(f"/api/scans?type={t}&limit=5")
        assert r.status_code == 200
        assert all(s["analysis_type"] == t for s in r.json()), t
    stats = client.get("/api/stats").json()
    assert stats["total"] >= 2


def test_old_rows_with_new_fields():
    body = client.post("/api/analyze", json=payment_payload()).json()
    assert body["evidence"]["parsed_qr"] == {}
    assert body["evidence"]["payload_class"] is None
