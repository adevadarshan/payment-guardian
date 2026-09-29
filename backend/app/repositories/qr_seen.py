# app/repositories/qr_seen.py — qr_seen persistence (Slice 3).
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import QrSeen


def get_by_hash(db: Session, payload_hash: str) -> QrSeen | None:
    return db.query(QrSeen).filter(QrSeen.payload_hash == payload_hash).first()


def record_sighting(db: Session, *, payload_hash: str, payload_class: str,
                    preview: str) -> tuple[QrSeen, bool]:
    """Lookup-or-record. Returns (row, is_first_sighting)."""
    row = get_by_hash(db, payload_hash)
    now = datetime.now(timezone.utc)
    if row is None:
        row = QrSeen(
            payload_hash=payload_hash,
            payload_class=payload_class,
            normalized_preview=preview[:120],
            first_seen_at=now,
            last_seen_at=now,
            times_seen=1,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row, True
    row.times_seen = (row.times_seen or 0) + 1
    row.last_seen_at = now
    db.commit()
    db.refresh(row)
    return row, False
