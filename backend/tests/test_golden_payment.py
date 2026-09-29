# tests/test_golden_payment.py — Slice 2 golden set (§6.6 of the Slice 2 plan).
# Each case asserts band AND expected reason codes. Any calibration change must
# update this table in the same commit with a written reason.
import pytest

from tests.conftest import client, payment_payload

DAY = "2026-09-29T14:00:00+00:00"
NIGHT = "2026-09-29T02:30:00+00:00"

CASES = [
    {
        "name": "safe grocery",
        "payload": payment_payload(
            amount=150.0, merchant_category="Groceries", sender_balance=5000.0,
            note="groceries", payee_id="shop@grocery", payee_name="Corner Shop",
        ),
        "timestamp": DAY,
        "score": 5, "level": "SAFE", "reasons": [],
    },
    {
        "name": "suspicious electronics",
        "payload": payment_payload(
            amount=3500.0, merchant_category="Electronics", sender_balance=20000.0,
            note="headphones", payee_id="vendor@upi", payee_name="Vendor",
        ),
        "timestamp": DAY,
        "score": 35, "level": "MEDIUM",
        "reasons": ["payment.amount_tier", "payment.category.ecommerce"],
    },
    {
        "name": "high-risk demo",
        "payload": payment_payload(
            amount=12000.0, merchant_category="Travel", sender_balance=50000.0,
            note=None, payee_id="unknown@upi", payee_name="Unknown",
        ),
        "timestamp": NIGHT,
        "score": 75, "level": "HIGH",
        "reasons": ["payment.amount_tier", "payment.category.travel",
                    "payment.unusual_hour", "payment.payee_unverified"],
    },
    {
        "name": "drain 95 percent",
        "payload": payment_payload(
            amount=9500.0, merchant_category="Groceries", sender_balance=10000.0,
            note=None, payee_id="shop@grocery", payee_name="Corner Shop",
        ),
        "timestamp": DAY,
        "score": 85, "level": "HIGH", "reasons": ["payment.balance_drain"],
    },
    {
        "name": "urgent note",
        "payload": payment_payload(
            amount=12000.0, merchant_category="Peer Transfer", sender_balance=50000.0,
            note="urgent verify kyc", payee_id="xx@bank", payee_name="X",
        ),
        "timestamp": DAY,
        "score": 92, "level": "HIGH", "reasons": ["payment.note.urgent"],
    },
    {
        # Sigmoid asymptote: at the maximum valid amount the floor is 74, so
        # amount alone cannot condemn — HIGH needs one more signal by design.
        "name": "near limit magnitude",
        "payload": payment_payload(
            amount=200000.0, merchant_category="Utilities", sender_balance=500000.0,
            note=None, payee_id="power@utility", payee_name="Power Co",
        ),
        "timestamp": DAY,
        "score": 74, "level": "MEDIUM", "reasons": ["payment.amount_magnitude"],
    },
    {
        "name": "info-only note stays safe",
        "payload": payment_payload(
            amount=800.0, merchant_category="Utilities", sender_balance=5000.0,
            note="refund claim", payee_id="power@utility", payee_name="Power Co",
        ),
        "timestamp": DAY,
        "score": 34, "level": "SAFE", "reasons": ["payment.note.credential"],
    },
    {
        "name": "night benign",
        "payload": payment_payload(
            amount=300.0, merchant_category="Groceries", sender_balance=5000.0,
            note=None, payee_id="shop@grocery", payee_name="Corner Shop",
        ),
        "timestamp": NIGHT,
        "score": 25, "level": "SAFE", "reasons": ["payment.unusual_hour"],
    },
    {
        "name": "crypto medium",
        "payload": payment_payload(
            amount=5000.0, merchant_category="Crypto", sender_balance=50000.0,
            note=None, payee_id="exchange@crypto", payee_name="Exchange",
        ),
        "timestamp": DAY,
        "score": 45, "level": "MEDIUM",
        "reasons": ["payment.amount_tier", "payment.category.crypto"],
    },
    {
        "name": "gambling drain",
        "payload": payment_payload(
            amount=60000.0, merchant_category="Gambling", sender_balance=65000.0,
            note=None, payee_id="bet@play", payee_name="Bet Site",
        ),
        "timestamp": DAY,
        "score": 85, "level": "HIGH", "reasons": ["payment.balance_drain"],
    },
]


def _analyze(case):
    body = dict(case["payload"])
    body["timestamp"] = case["timestamp"]
    r = client.post("/api/analyze", json=body)
    assert r.status_code == 200, (case["name"], r.text)
    return r.json()


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_golden_payment(case):
    body = _analyze(case)
    assert body["risk_score"] == case["score"], case["name"]
    assert body["risk_level"] == case["level"], case["name"]
    codes = [reason["code"] for reason in body["reasons"]]
    for expected in case["reasons"]:
        assert expected in codes, (case["name"], codes)
    if case["level"] in ("MEDIUM", "HIGH"):
        assert codes, case["name"]
    assert body["pipeline_version"] == "slice-4"
    assert body["model"]["backend"] == "none"
    assert body["payment_summary"] is not None
    assert body["payment_summary"]["payee_id"] == case["payload"]["payment"]["payee_id"]


def test_reasons_ordered_by_contribution_desc():
    body = _analyze(CASES[4])  # urgent note: 50, 25, 12, 5
    codes = [r["code"] for r in body["reasons"]]
    assert codes[0] == "payment.note.urgent"
    contribs = [s["contribution"] for s in body["signals"] if s["name"] != "payment.base"]
    assert contribs == sorted(contribs, reverse=True)
