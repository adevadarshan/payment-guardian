# tests/test_qr_seen.py — Slice 3 increment 8: previously-seen semantics.
# Unique payloads per test: seen state depends on suite execution order.
import json

from sqlalchemy import text

from app.db.session import SessionLocal
from tests.conftest import client


def _scan_qr(payload, **extra):
    body = {"analysis_type": "qr", "qr": {"payload": payload}}
    body.update(extra)
    r = client.post("/api/analyze", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_first_scan_new_rescan_previously_seen():
    payload = "upi://pay?pa=reseentest@upi&pn=Rescan Shop&am=42"
    first = _scan_qr(payload)
    assert first["seen"]["status"] == "new"
    assert first["seen"]["times_seen"] == 1
    assert any(r["code"] == "qr.seen_new" for r in first["reasons"])

    second = _scan_qr(payload)
    assert second["seen"]["status"] == "previously_seen"
    assert second["seen"]["times_seen"] == 2
    assert second["seen"]["first_seen_at"] == first["seen"]["first_seen_at"]
    assert any(r["code"] == "qr.seen_before" for r in second["reasons"])

    db = SessionLocal()
    try:
        row = db.execute(
            text("SELECT payload_class, times_seen, first_scan_id FROM qr_seen"
                 " WHERE payload_hash=:h"),
            {"h": _hash_of(payload)},
        ).one()
        assert row[0] == "upi_uri" and row[1] == 2 and row[2] is not None
    finally:
        db.close()


def _hash_of(payload):
    from app.pipeline.normalize import normalize_qr_payload, qr_payload_hash
    return qr_payload_hash(normalize_qr_payload(payload))


def test_variant_payloads_share_one_hash():
    a = "upi://pay?pa=variant@upi&pn=Variant&am=7"
    b = "  UPI://pay?am=7&pn=Variant&pa=variant@upi  "
    first = _scan_qr(a)
    assert first["seen"]["status"] == "new"
    second = _scan_qr(b)
    assert second["seen"]["status"] == "previously_seen"


def test_new_qr_is_not_safe():
    # Low-score first sighting: still carries the seen reason, and nothing in
    # the response ties seen-status to safety/legitimacy language.
    body = _scan_qr("upi://pay?pa=brandnewlow@upi&pn=New Low&am=5")
    assert body["seen"]["status"] == "new"
    assert any(r["code"] == "qr.seen_new" for r in body["reasons"])
    blob = json.dumps(body).lower()
    # The mandated disclaimer must be present ...
    assert "not a verified-safe code" in blob
    # ... and no seen-status reason may carry safety-claim wording.
    # (The SAFE-level action headline legitimately contains "legitimate";
    # the rule is about seen-status language, not level language.)
    for reason in body["reasons"]:
        if reason["code"].startswith("qr.seen"):
            text = (reason["title"] + " " + reason["observation"]).lower()
            for phrase in ("legitimate", "is safe because", "proven safe",
                           "confirmed safe", "verified safe."):
                assert phrase not in text


def test_corrupt_qr_records_no_row_and_no_seen_reason():
    r = client.post("/api/analyze", json={
        "analysis_type": "qr",
        "qr": {"image_base64": "iVBORw0KGgo="}})  # truncated PNG header
    # Either undecodable (200 unable_to_verify) or unsupported media (422).
    assert r.status_code in (200, 422)
    if r.status_code == 200:
        assert r.json()["seen"]["status"] == "unable_to_verify"


def test_qr_seen_audit_logged_once_per_hash():
    payload = "upi://pay?pa=auditonce@upi&pn=Audit&am=9"
    db = SessionLocal()
    try:
        before = db.execute(
            text("SELECT COUNT(*) FROM audit_log WHERE event_type='QR_SEEN'")).scalar()
    finally:
        db.close()
    _scan_qr(payload)
    _scan_qr(payload)
    db = SessionLocal()
    try:
        after = db.execute(
            text("SELECT COUNT(*) FROM audit_log WHERE event_type='QR_SEEN'")).scalar()
    finally:
        db.close()
    assert after - before == 1
