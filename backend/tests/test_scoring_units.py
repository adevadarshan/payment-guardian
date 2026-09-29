# tests/test_scoring_units.py — Slice 2 unit tests: rules, thresholds,
# mapping, parity, determinism, stub removal, reasons invariant.
from app.categories import ALLOWED_CATEGORIES, CATEGORIES
from app.pipeline import rules
from app.pipeline.thresholds import classify
from tests.conftest import client, payment_payload


def test_threshold_boundaries_server_owned():
    assert classify(0) == "SAFE"
    assert classify(34) == "SAFE"
    assert classify(35) == "MEDIUM"
    assert classify(74) == "MEDIUM"
    assert classify(75) == "HIGH"
    assert classify(100) == "HIGH"


def test_all_24_categories_resolve():
    assert len(ALLOWED_CATEGORIES) == 24 == len(CATEGORIES)
    for label in ALLOWED_CATEGORIES:
        points, known = rules.category_points(label)
        assert known, label
        assert CATEGORIES[label]["type"] in ("PAYMENT", "DEBIT", "TRANSFER", "CASH_OUT")
    assert rules.category_points("Nope") == (0, False)


def test_amount_tier_boundaries():
    assert rules.amount_tier(0)[0] == 0
    assert rules.amount_tier(499)[0] == 0
    assert rules.amount_tier(500)[0] == 4
    assert rules.amount_tier(1999)[0] == 4
    assert rules.amount_tier(2000)[0] == 10
    assert rules.amount_tier(9999)[0] == 15
    assert rules.amount_tier(10000)[0] == 25
    assert rules.amount_tier(19999)[0] == 25
    assert rules.amount_tier(20000)[0] == 30
    assert rules.amount_tier(49999)[0] == 30
    assert rules.amount_tier(50000)[0] == 35
    assert rules.amount_tier(99999)[0] == 35
    assert rules.amount_tier(100000)[0] == 45
    assert rules.amount_tier(200000)[0] == 45


def test_drain_and_magnitude():
    assert rules.drain_ratio(9500.0, 10000.0) > 0.90
    assert rules.drain_ratio(100.0, 5000.0) < 0.60
    assert rules.magnitude_floor(150.0) < 5  # must not move benign scores
    # Sigmoid asymptote at the maximum valid amount: 74, never 75 alone.
    assert rules.magnitude_floor(200000.0) == 74


def test_note_families_and_urgent_wins():
    assert rules.note_hits(None) == (None, [])
    assert rules.note_hits("groceries")[0] is None
    fam, phrases = rules.note_hits("URGENT: verify your OTP now")
    assert fam == "urgent" and "otp" in phrases and "urgent" in phrases
    fam, phrases = rules.note_hits("refund claim for kyc")
    assert fam == "info" and set(phrases) == {"refund", "claim", "kyc"}
    # word boundaries: no substring false positives
    assert rules.note_hits("headphones")[0] is None


def test_payee_unverified():
    assert rules.payee_unverified(None) is True
    assert rules.payee_unverified("   ") is True
    assert rules.payee_unverified("UNKNOWN") is True
    assert rules.payee_unverified("Corner Shop") is False


def test_client_gate_parity_vectors():
    bad = [
        payment_payload(amount=0),
        payment_payload(amount=200001),
        payment_payload(amount=6000.0),
        payment_payload(payee_id="not-an-upi-id"),
        payment_payload(merchant_category="Nope"),
    ]
    for payload in bad:
        r = client.post("/api/analyze", json=payload)
        assert r.status_code == 422, payload
        assert r.json()["error"]["code"] == "validation_error"


def test_level_and_type_filters_reject_garbage():
    assert client.get("/api/scans?level=BOGUS").status_code == 422
    assert client.get("/api/scans?type=bogus").status_code == 422
    assert client.get("/api/scans?level=HIGH").status_code == 200
    assert client.get("/api/scans?type=payment").status_code == 200
    assert client.get("/api/scans?type=url").status_code == 200


def test_stats_aggregation():
    before = client.get("/api/stats").json()["total"]
    client.post("/api/analyze", json=payment_payload(amount=150.0))
    after = client.get("/api/stats").json()
    assert after["total"] == before + 1
    assert after["safe"] + after["medium"] + after["high"] == after["total"]
    assert 0.0 <= after["fraud_rate"] <= 1.0


def test_determinism_identical_inputs():
    body = payment_payload(amount=1234.0, note="test")
    body["timestamp"] = "2026-09-29T14:00:00+00:00"
    first = client.post("/api/analyze", json=body).json()
    second = client.post("/api/analyze", json=body).json()
    for key in ("risk_score", "reasons", "signals", "evidence", "recommended_action"):
        assert first[key] == second[key]


def test_stub_removed_and_version():
    body = client.post("/api/analyze", json=payment_payload()).json()
    assert body["pipeline_version"] == "slice-4"
    assert all(r["code"] != "pipeline.not_implemented" for r in body["reasons"])


def test_reasons_invariant_medium_high():
    payload = payment_payload(
        amount=12000.0, merchant_category="Travel", sender_balance=50000.0,
        payee_id="unknown@upi", payee_name="Unknown",
    )
    payload["timestamp"] = "2026-09-29T02:30:00+00:00"
    body = client.post("/api/analyze", json=payload).json()
    assert body["risk_level"] == "HIGH"
    assert len(body["reasons"]) >= 1
