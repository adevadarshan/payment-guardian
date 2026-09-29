# tests/test_qr_payload.py — Slice 3 increment 6: classification, UPI parsing,
# routing into shared analyzers, QR+context composition. No image decoding yet.
from app.analyzers.qr_analyzer import analyze_qr_payload, classify_payload, extract_upi
from tests.conftest import client


def test_classify_payload_ordered_predicates():
    assert classify_payload("upi://pay?pa=x@y") == "upi_uri"
    assert classify_payload("UPI://pay?pa=x@y") == "upi_uri"
    assert classify_payload("https://example.com/a") == "url"
    assert classify_payload("BEGIN:VCARD\nFN:Shop") == "contact"
    assert classify_payload("tel:+911234567890") == "contact"
    assert classify_payload("bitcoin:1A2b3C") == "crypto"
    assert classify_payload("hello there friend") == "text"
    assert classify_payload("   ") == "unknown"
    assert classify_payload("!!!") == "unknown"


def test_extract_upi_fields():
    parsed = extract_upi("upi://pay?pa=shop@upi&pn=Corner+Shop&am=250.5&cu=INR&tr=ABC123&tn=groceries&mc=5411")
    assert parsed["pa"] == "shop@upi"
    assert parsed["pn"] == "Corner Shop"
    assert parsed["am"] == 250.5
    assert parsed["cu"] == "INR"
    assert parsed["tr"] == "ABC123"
    assert parsed["mc"] == "5411"
    partial = extract_upi("upi://pay?pa=shop@upi")
    assert partial["pa"] == "shop@upi" and partial["am"] is None
    bad_amount = extract_upi("upi://pay?pa=shop@upi&am=lots")
    assert bad_amount["am"] is None


def test_upi_routing_and_mismatch():
    signals, matched, info = analyze_qr_payload("upi://pay?pa=shop@upi&pn=Corner Shop&am=250")
    assert info["class"] == "upi_uri"
    assert info["parsed"]["pa"] == "shop@upi"
    signals, _, _ = analyze_qr_payload("upi://pay?pa=random123@upi&pn=Best Store&am=5000")
    names = [s.name for s in signals]
    assert "qr.merchant_mismatch" in names
    assert "payment.amount_tier" in names  # payment-family codes reused


def test_url_in_qr_routes_to_url_analyzer():
    signals, _, _ = analyze_qr_payload("http://paypal.com.secure-login.xyz/verify?email=x")
    assert any(s.name.startswith("url.") for s in signals)


def test_text_in_qr_routes_to_message_analyzer():
    signals, _, _ = analyze_qr_payload("Your account blocked. Verify OTP now.")
    assert any(s.name.startswith("message.") for s in signals)


def test_qr_with_payment_context_composition():
    r = client.post("/api/analyze", json={
        "analysis_type": "qr",
        "qr": {"payload": "upi://pay?pa=shop@upi&pn=Shop&am=250"},
        "payment_context": {"amount": 12000.0, "sender_balance": 50000.0},
    })
    assert r.status_code == 200
    names = [s["name"] for s in r.json()["signals"]]
    assert "qr.amount_conflict" in names
    assert any(n.startswith("payment_context.") for n in names)


def test_qr_payload_end_to_end_seen_new_on_first_scan():
    # Unique payload: first sighting in this suite -> "new".
    r = client.post("/api/analyze", json={
        "analysis_type": "qr",
        "qr": {"payload": "upi://pay?pa=firstsighting@upi&pn=First Shop&am=10"}})
    assert r.status_code == 200
    body = r.json()
    assert body["evidence"]["payload_class"] == "upi_uri"
    assert body["evidence"]["parsed_qr"]["pa"] == "firstsighting@upi"
    assert body["evidence"]["decoded"] is True
    assert body["seen"]["status"] == "new"
    assert any(reason["code"] == "qr.seen_new" for reason in body["reasons"])


def test_qr_non_image_bytes_rejected():
    r = client.post("/api/analyze", json={
        "analysis_type": "qr", "qr": {"image_base64": "aGVsbG8="}})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "unsupported_media"
