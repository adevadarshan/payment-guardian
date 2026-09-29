# app/repositories/audit.py

from sqlalchemy.orm import Session

from app.db.models import AuditLog


def list_entries(db: Session, limit: int = 200,
                 user_id: str | None = None) -> list[AuditLog]:
    query = db.query(AuditLog).order_by(AuditLog.id.asc())
    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    return query.limit(max(1, min(limit, 1000))).all()
