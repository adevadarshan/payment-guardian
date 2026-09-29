# tests/test_contract_frozen.py — Slice 4 increment 6: additive-only contract.
# Frozen Slice 3 example payloads replayed; responses must remain
# superset-compatible (all old fields present, same values where deterministic).
from tests.conftest import client, payment_payload


def test_payment_response_superset_compatible():
    body = payment_payload()
    body["timestamp"] = "2026-09-29T14:00:00+00:00"
    data = client.post("/api/analyze", json=body).json()
    for field in ("scan_id", "analysis_type", "risk_score", "risk_level",
                  "reasons", "signals", "evidence", "seen",
                  "recommended_action", "advisory", "model",
                  "pipeline_version", "created_at", "payment_summary"):
        assert field in data, field
    assert (data["risk_score"], data["risk_level"]) == (5, "SAFE")
    assert data["advisory"]["status"] == "disabled"
    assert data["model"]["backend"] == "none"


def test_message_url_qr_shapes_superset_compatible():
    cases = [
        ({"analysis_type": "message", "message": {"text": "Hello friend, see you soon"}}, "SAFE"),
        ({"analysis_type": "url", "url": {"url": "https://www.hdfcbank.com/"}}, "SAFE"),
        ({"analysis_type": "qr", "qr": {"payload": "upi://pay?pa=frozen@upi&pn=Frozen&am=5"}},
         "SAFE"),
    ]
    for body, level in cases:
        data = client.post("/api/analyze", json=body).json()
        assert data["risk_level"] == level, body
        assert set(data["evidence"]) >= {"extracted_urls", "matched_phrases",
                                         "qr_payload", "decoded", "parsed_qr",
                                         "payload_class", "qr_decode"}
