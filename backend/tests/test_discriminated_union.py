# tests/test_discriminated_union.py — Slice 3 increment 2: contract shapes.
from tests.conftest import client, payment_payload


def _ok_shape(body, analysis_type):
    for field in (
        "scan_id", "analysis_type", "risk_score", "risk_level", "reasons",
        "signals", "evidence", "seen", "recommended_action", "advisory",
        "model", "pipeline_version", "created_at", "payment_summary",
    ):
        assert field in body, field
    assert body["analysis_type"] == analysis_type


def test_payment_still_works():
    r = client.post("/api/analyze", json=payment_payload())
    assert r.status_code == 200
    _ok_shape(r.json(), "payment")


def test_qr_image_path_exists():
    # Image decoding is wired from increment 7: invalid base64 -> 422 envelope.
    r = client.post("/api/analyze", json={
        "analysis_type": "qr", "qr": {"image_base64": "!!!not-base64!!!"}})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "unsupported_media"


def test_message_and_url_score_through_pipeline():
    r = client.post("/api/analyze", json={
        "analysis_type": "message", "message": {"text": "Your account will be blocked. Verify OTP now."}})
    assert r.status_code == 200
    _ok_shape(r.json(), "message")
    assert r.json()["seen"]["status"] == "not_applicable"
    r = client.post("/api/analyze", json={
        "analysis_type": "url", "url": {"url": "http://paypal.com.secure-login.xyz/verify?email=x"}})
    assert r.status_code == 200
    _ok_shape(r.json(), "url")
    assert r.json()["evidence"]["extracted_urls"] == ["http://paypal.com.secure-login.xyz/verify?email=x"]


def test_mismatched_and_missing_blocks_rejected():
    bad = [
        {"analysis_type": "payment"},  # missing block
        {"analysis_type": "message"},  # missing block
        {"analysis_type": "qr", "qr": {}},  # neither image nor payload
        {"analysis_type": "url"},  # missing block
        dict(payment_payload(), message={"text": "hello there friend"}),  # extra block
        dict(payment_payload(), payment_context={"amount": 10.0}),  # ctx with payment
        {"analysis_type": "message", "message": {"text": ""}},  # empty text
    ]
    for payload in bad:
        r = client.post("/api/analyze", json=payload)
        assert r.status_code == 422, payload
        assert r.json()["error"]["code"] == "validation_error", payload
