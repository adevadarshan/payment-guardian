# app/api/routes/audit.py (Slice 4: + user scoping on list; verify stays global)
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import scoped_user_id
from app.db.session import get_db
from app.repositories import audit as audit_repo
from app.services import audit_service

router = APIRouter()


class AuditEntryOut(BaseModel):
    id: int
    event_type: str
    entity_type: str
    entity_id: str
    payload: dict
    previous_hash: str
    entry_hash: str
    created_at: str


@router.get("/audit", response_model=list[AuditEntryOut])
def list_audit(limit: int = 200, db: Session = Depends(get_db),
               user_id: str | None = Depends(scoped_user_id)):
    return [
        AuditEntryOut(
            id=e.id,
            event_type=e.event_type,
            entity_type=e.entity_type,
            entity_id=e.entity_id,
            payload=e.payload,
            previous_hash=e.previous_hash,
            entry_hash=e.entry_hash,
            created_at=str(e.created_at),
        )
        for e in audit_repo.list_entries(db, limit=limit, user_id=user_id)
    ]


@router.post("/audit/verify")
def verify_audit(db: Session = Depends(get_db),
                 user_id: str | None = Depends(scoped_user_id)):
    # Global chain validity + counts only: no per-entry data crosses users.
    _ = user_id  # auth enforced by the dependency; scope intentionally global
    return audit_service.verify_chain(db)
