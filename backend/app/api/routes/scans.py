# app/api/routes/scans.py (Slice 4: + user scoping; shapes unchanged)
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import scoped_user_id
from app.config import settings
from app.db.session import get_db
from app.repositories import scans as scan_repo
from app.schemas.analyze import AnalysisResult, ScanSummary

router = APIRouter()


def _label(row) -> str:
    stored_label = (row.result_json or {}).get("label")
    if stored_label:
        return stored_label
    if row.analysis_type == "payment":
        return f"Rs.{row.payment_amount:g} to {row.payment_payee_id}"
    return row.analysis_type


@router.get("/scans", response_model=list[ScanSummary])
def list_scans(
    limit: int = 50,
    level: Literal["SAFE", "MEDIUM", "HIGH"] | None = None,
    type: Literal["payment", "message", "url", "qr"] | None = None,
    db: Session = Depends(get_db),
    user_id: str | None = Depends(scoped_user_id),
):
    # Literal mismatches raise RequestValidationError -> the 422 envelope in main.py.
    rows = scan_repo.list_scans(db, limit=limit, level=level,
                                analysis_type=type, user_id=user_id)
    return [
        ScanSummary(
            scan_id=r.id,
            analysis_type=r.analysis_type,  # type: ignore[arg-type]
            risk_score=r.risk_score,
            risk_level=r.risk_level,  # type: ignore[arg-type]
            label=_label(r),
            created_at=str(r.created_at),
        )
        for r in rows
    ]


@router.get("/scans/{scan_id}", response_model=AnalysisResult)
def get_scan(scan_id: str, db: Session = Depends(get_db),
             user_id: str | None = Depends(scoped_user_id)):
    row = scan_repo.get_scan(db, scan_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    # Cross-user reads are 404 (not 403) to avoid an id-existence oracle.
    if settings.AUTH_REQUIRED and row.user_id != user_id:
        raise HTTPException(status_code=404, detail="Scan not found")
    return row.result_json
