# app/services/audit_service.py — clean-room hash-chained audit log (Slice 1).
# Canonical serialisation: sorted keys, compact separators, ASCII. Any change
# to this function invalidates existing chains — treat it as frozen.

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import AuditLog

GENESIS_HASH = "0" * 64


def _canonical(entry: dict) -> str:
    return json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(entry: dict) -> str:
    return hashlib.sha256(_canonical(entry).encode("utf-8")).hexdigest()


def append_entry(
    db: Session,
    *,
    event_type: str,
    entity_type: str,
    entity_id: str,
    payload: dict,
    user_id: str | None = None,
) -> AuditLog:
    last = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    previous_hash = last.entry_hash if last else GENESIS_HASH
    created_at_str = datetime.now(timezone.utc).isoformat()
    entry_hash = _hash(
        {
            "event_type": event_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "payload": payload,
            "previous_hash": previous_hash,
            "created_at_str": created_at_str,
        }
    )
    row = AuditLog(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
        previous_hash=previous_hash,
        entry_hash=entry_hash,
        created_at_str=created_at_str,
        user_id=user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def verify_chain(db: Session) -> dict:
    entries = db.query(AuditLog).order_by(AuditLog.id.asc()).all()
    expected_prev = GENESIS_HASH
    for entry in entries:
        if entry.previous_hash != expected_prev:
            return {
                "valid": False,
                "broken_at_id": entry.id,
                "reason": f"Previous hash mismatch at entry {entry.id}",
            }
        recomputed = _hash(
            {
                "event_type": entry.event_type,
                "entity_type": entry.entity_type,
                "entity_id": entry.entity_id,
                "payload": entry.payload,
                "previous_hash": entry.previous_hash,
                "created_at_str": entry.created_at_str,
            }
        )
        if recomputed != entry.entry_hash:
            return {
                "valid": False,
                "broken_at_id": entry.id,
                "reason": f"Hash mismatch at entry {entry.id}: data was modified after logging",
            }
        expected_prev = entry.entry_hash
    return {"valid": True, "entry_count": len(entries)}
