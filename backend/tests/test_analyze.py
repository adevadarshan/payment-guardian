# Slice 1 backend tests: health, categories, stub contract, validation.
from conftest import client, payment_payload


def test_health_ok():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["model_backend"] == "none"


def test_categories_endpoint():
    r = client.get("/api/categories")
    assert r.status_code == 200
    cats = r.json()
    assert len(cats) == 24
    labels = [c["label"] for c in cats]
    assert len(set(labels)) == 24
    for c in cats:
        assert c["key"] and c["type"] in ("PAYMENT", "DEBIT", "TRANSFER", "CASH_OUT")
        assert isinstance(c["risk_weight"], (int, float))


def test_analyze_real_contract():
    r = client.post("/api/analyze", json=payment_payload())
    assert r.status_code == 200
    body = r.json()
    for field in (
        "scan_id", "analysis_type", "risk_score", "risk_level", "reasons",
        "signals", "evidence", "seen", "recommended_action", "advisory",
        "model", "pipeline_version", "created_at", "payment_summary",
    ):
        assert field in body, f"missing {field}"
    assert body["analysis_type"] == "payment"
    assert body["pipeline_version"] == "slice-4"
    assert body["model"]["backend"] == "none"
    assert body["advisory"]["status"] == "disabled"
    assert body["seen"]["status"] == "not_applicable"
    assert "pipeline.not_implemented" not in [reason["code"] for reason in body["reasons"]]
    assert body["payment_summary"]["payee_id"] == "shop@grocery"
    assert body["payment_summary"]["amount"] == 150.0

    # Persistence regression guard: every accepted payment field stored.
    scan_id = body["scan_id"]
    got = client.get(f"/api/scans/{scan_id}")
    assert got.status_code == 200
    assert got.json()["scan_id"] == scan_id


def test_analyze_validation():
    cases = [
        payment_payload(amount=0),
        payment_payload(amount=300000),
        payment_payload(amount=6000.0),  # exceeds sender_balance 5000
        payment_payload(merchant_category="Not A Category"),
        payment_payload(payee_id="not-an-upi-id"),
        {"analysis_type": "payment"},  # missing payment block
        {"analysis_type": "message", "payment": payment_payload()["payment"]},
    ]
    for payload in cases:
        r = client.post("/api/analyze", json=payload)
        assert r.status_code == 422, payload
        body = r.json()
        assert body["error"]["code"] == "validation_error"
