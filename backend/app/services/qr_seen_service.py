# app/services/qr_seen_service.py — previously-seen lookup facade (Slice 3).
# Thin wrapper over the repository so the route stays free of query logic.
from sqlalchemy.orm import Session

from app.db.models import QrSeen
from app.repositories import qr_seen as qr_seen_repo


def check_and_record(db: Session, *, payload_hash: str, payload_class: str,
                     preview: str) -> tuple[QrSeen, bool]:
    """Returns (row, is_first_sighting). Never logs payloads."""
    return qr_seen_repo.record_sighting(
        db, payload_hash=payload_hash, payload_class=payload_class, preview=preview)
