# app/api/routes/stats.py (Slice 4: + user scoping; shape unchanged)
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import scoped_user_id
from app.db.models import Scan
from app.db.session import get_db

router = APIRouter()


class StatsOut(BaseModel):
    total: int
    safe: int
    medium: int
    high: int
    fraud_rate: float


@router.get("/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db),
              user_id: str | None = Depends(scoped_user_id)):
    base = db.query(Scan)
    if user_id is not None:
        base = base.filter(Scan.user_id == user_id)
    total = base.with_entities(func.count(Scan.id)).scalar() or 0
    safe = base.filter(Scan.risk_level == "SAFE").with_entities(func.count(Scan.id)).scalar() or 0
    medium = base.filter(Scan.risk_level == "MEDIUM").with_entities(func.count(Scan.id)).scalar() or 0
    high = base.filter(Scan.risk_level == "HIGH").with_entities(func.count(Scan.id)).scalar() or 0
    return StatsOut(
        total=total,
        safe=safe,
        medium=medium,
        high=high,
        fraud_rate=round(high / total, 4) if total else 0.0,
    )
