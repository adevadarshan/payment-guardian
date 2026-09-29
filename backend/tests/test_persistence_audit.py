# Slice 1 backend tests: persistence, listing, audit chain.
import json

from sqlalchemy import text

from app.db.session import SessionLocal
from conftest import client, payment_payload


def _db():
    return SessionLocal()


def test_persistence_roundtrip_all_fields():
    payload = payment_payload(
        amount=2500.0,
        payee_id="vendor@upi",
        payee_name="Vendor",
        sender_balance=10000.0,
        note="test note",
        channel="upi",
        merchant_category="Electronics",
    )
    scan_id = client.post("/api/analyze", json=payload).json()["scan_id"]
    db = _db()
    try:
        row = db.execute(
            text("SELECT payment_amount, payment_payee_id, payment_sender_balance,"
                 " payment_note, payment_merchant_category, payment_currency,"
                 " payment_payee_name, payment_channel FROM scans WHERE id=:i"),
            {"i": scan_id},
        ).one()
        assert row[0] == 2500.0
        assert row[1] == "vendor@upi"
        assert row[2] == 10000.0
        assert row[3] == "test note"
        assert row[4] == "Electronics"
        assert row[5] == "INR"
        assert row[6] == "Vendor"
        assert row[7] == "upi"
    finally:
        db.close()


def test_scans_listing_newest_first_respects_limit():
    for i in range(3):
        client.post("/api/analyze", json=payment_payload(amount=100.0 + i))
    r = client.get("/api/scans?limit=2")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_audit_chain_append_and_verify():
    # Append entries through the public path, then verify via the endpoint.
    client.post("/api/analyze", json=payment_payload())
    ok = client.post("/api/audit/verify").json()
    assert ok["valid"] is True
    assert ok["entry_count"] >= 1

    db = _db()
    try:
        target = db.execute(text("SELECT id, payload FROM audit_log ORDER BY id DESC LIMIT 1")).one()
        broken_id, original = target[0], target[1]
        tampered = dict(json.loads(original) if isinstance(original, str) else original)
        tampered["risk_score"] = 9999
        db.execute(
            text("UPDATE audit_log SET payload=:p WHERE id=:i"),
            {"p": json.dumps(tampered), "i": broken_id},
        )
        db.commit()
        bad = client.post("/api/audit/verify").json()
        assert bad["valid"] is False
        assert bad["broken_at_id"] == broken_id

        db.execute(
            text("UPDATE audit_log SET payload=:p WHERE id=:i"),
            {"p": original if isinstance(original, str) else json.dumps(original), "i": broken_id},
        )
        db.commit()
    finally:
        db.close()
    fixed = client.post("/api/audit/verify").json()
    assert fixed["valid"] is True


def test_audit_list_endpoint():
    r = client.get("/api/audit?limit=5")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
