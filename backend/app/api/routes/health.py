# app/api/routes/health.py (Slice 4: + capability disclosure, additive)
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.ml import registry as ml_registry

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"
    handle = ml_registry.get(settings.MODEL_BACKEND)
    advisory_mode = "disabled"
    if settings.ADVISORY_ENABLED:
        advisory_mode = "stub" if settings.ADVISORY_PROVIDER == "stub" else settings.ADVISORY_PROVIDER
    return {
        "status": "ok",
        "db": db_status,
        "model_backend": settings.MODEL_BACKEND,
        "ml_artifacts": handle is not None,
        "ml_version": handle.version if handle else None,
        "advisory": advisory_mode,
        "auth_required": settings.AUTH_REQUIRED,
        "pipeline_version": settings.PIPELINE_VERSION,
    }
