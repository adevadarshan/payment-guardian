# app/repositories/scans.py — plain persistence functions (Slice 1).

from sqlalchemy.orm import Session

from app.db.models import Scan


def create_scan(db: Session, user_id: str | None = None, **fields) -> Scan:
    row = Scan(user_id=user_id, **fields)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_scans(
    db: Session,
    limit: int = 50,
    level: str | None = None,
    analysis_type: str | None = None,
    user_id: str | None = None,
) -> list[Scan]:
    query = db.query(Scan).order_by(Scan.created_at.desc(), Scan.id.desc())
    if level is not None:
        query = query.filter(Scan.risk_level == level)
    if analysis_type is not None:
        query = query.filter(Scan.analysis_type == analysis_type)
    if user_id is not None:
        query = query.filter(Scan.user_id == user_id)
    return query.limit(max(1, min(limit, 200))).all()


def get_scan(db: Session, scan_id: str) -> Scan | None:
    return db.query(Scan).filter(Scan.id == scan_id).first()
