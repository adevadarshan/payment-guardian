# app/api/routes/analyze.py — Slice 3: dispatch through pipeline/run.py.
# Payment path preserves Slice 2 semantics exactly (see payment_analyzer).
# Hour-of-day uses server-trusted time in production; the request timestamp
# is honoured only when ALLOW_CLIENT_HOUR is enabled (deterministic tests).
# QR images are server-decoded (authority); client payloads are convenience.

import base64
import binascii
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.categories import CATEGORIES
from app.config import settings
from app.db.session import get_db
from app.api.deps import limit_analyze, scoped_user_id
from app.pipeline import run as pipeline
from app.analyzers.qr_analyzer import DecodeError
from app.repositories import scans as scan_repo
from app.schemas.analyze import (
    Advisory,
    AnalysisResult,
    AnalyzeRequest,
    Evidence,
    ModelInfo,
    PaymentSummary,
    Reason,
    RecommendedAction,
    SeenInfo,
)
from app.services import audit_service

router = APIRouter()


def _request_hour(timestamp: str | None) -> int | None:
    """Server-trusted hour. Client timestamp only when explicitly test-enabled."""
    if timestamp and settings.ALLOW_CLIENT_HOUR:
        try:
            parsed = datetime.fromisoformat(timestamp)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.hour
        except ValueError:
            return None
    return datetime.now(timezone.utc).hour


@router.post("/analyze", response_model=AnalysisResult)
def analyze(
    req: AnalyzeRequest,
    db: Session = Depends(get_db),
    _: None = Depends(limit_analyze),
    user_id: str | None = Depends(scoped_user_id),
):
    image_bytes: bytes | None = None
    if req.analysis_type == "qr":
        assert req.qr is not None
        if req.qr.image_base64:
            raw_b64 = req.qr.image_base64.strip()
            # Pre-cap the transport encoding before decoding into memory.
            if len(raw_b64) > 8 * 1024 * 1024:
                return JSONResponse(
                    status_code=413,
                    content={"error": {
                        "code": "too_large",
                        "message": "QR image exceeds the 5 MB limit.",
                    }},
                )
            try:
                image_bytes = base64.b64decode(raw_b64, validate=True)
            except (binascii.Error, ValueError):
                return JSONResponse(
                    status_code=422,
                    content={"error": {
                        "code": "unsupported_media",
                        "message": "image_base64 is not valid base64.",
                    }},
                )

    try:
        verdict = pipeline.analyze_request(
            analysis_type=req.analysis_type,
            payment=req.payment,
            message=req.message,
            url=req.url,
            qr=req.qr,
            payment_context=req.payment_context,
            hour=_request_hour(req.timestamp),
            image_bytes=image_bytes,
            qr_limits={"max_bytes": settings.QR_MAX_MB * 1024 * 1024,
                       "max_megapixels": settings.QR_MAX_MEGAPIXELS},
            store_qr_payload=settings.STORE_QR_PAYLOADS,
        )
    except DecodeError as exc:
        kind = str(exc)
        if kind == "too_large":
            return JSONResponse(
                status_code=413,
                content={"error": {
                    "code": "too_large",
                    "message": "QR image exceeds the size/pixel limit.",
                }},
            )
        return JSONResponse(
            status_code=422,
            content={"error": {
                "code": "unsupported_media",
                "message": "QR image type is not supported.",
            }},
        )
    now = datetime.now(timezone.utc).isoformat()
    payment = req.payment

    # QR seen detection (needs the DB; run.py stays DB-free). Re-scores nothing:
    # seen contributes an informational reason + action wording only.
    qr_first_sighting = False
    qr_lookup_hash: str | None = None
    seen_status = verdict["seen_status"]
    seen_first_at: str | None = None
    seen_times: int | None = None
    lookup = verdict.get("qr_lookup")
    if req.analysis_type == "qr" and lookup:
        from app.pipeline import explain as _explain
        from app.services import qr_seen_service
        row_seen, is_first = qr_seen_service.check_and_record(
            db,
            payload_hash=lookup["payload_hash"],
            payload_class=lookup["payload_class"],
            preview=lookup["preview"],
        )
        seen_status = "new" if is_first else "previously_seen"
        qr_first_sighting = is_first
        qr_lookup_hash = lookup["payload_hash"]
        seen_first_at = str(row_seen.first_seen_at)
        seen_times = row_seen.times_seen
        reason = _explain.seen_reason(
            seen_status, first_seen_at=seen_first_at, times_seen=seen_times)
        if reason is not None:
            verdict["reasons"].append(reason)
            verdict["signals"].append({
                "name": "qr.seen", "source": "rule", "value": None,
                "weight": None, "contribution": 0,
            })
        verdict["recommended_action"] = _explain.select_action(
            verdict["risk_level"], "qr", seen_status=seen_status)
        verdict["input_echo"]["input_qr_payload_hash"] = lookup["payload_hash"]
    result = AnalysisResult(
        scan_id="",  # filled after persistence
        analysis_type=req.analysis_type,
        risk_score=verdict["risk_score"],
        risk_level=verdict["risk_level"],
        reasons=[Reason(**r) for r in verdict["reasons"]],
        signals=verdict["signals"],
        evidence=Evidence(**verdict["evidence"]),
        seen=SeenInfo(status=seen_status, first_seen_at=seen_first_at,
                      times_seen=seen_times),
        recommended_action=RecommendedAction(**verdict["recommended_action"]),
        advisory=Advisory(status="disabled"),
        model=ModelInfo(backend=verdict.get("model", {}).get("backend", settings.MODEL_BACKEND),
                        version=(verdict.get("model", {}) or {}).get("version")),
        pipeline_version=settings.PIPELINE_VERSION,
        created_at=now,
        payment_summary=PaymentSummary(
            amount=payment.amount,
            payee_id=payment.payee_id,
            payee_name=payment.payee_name,
            merchant_category=payment.merchant_category,
            channel=payment.channel,
            sender_balance=payment.sender_balance,
        ) if payment is not None else None,
    )

    row = scan_repo.create_scan(
        db,
        user_id=user_id,
        analysis_type=req.analysis_type,
        risk_score=result.risk_score,
        risk_level=result.risk_level,
        pipeline_version=result.pipeline_version,
        payment_amount=payment.amount if payment else None,
        payment_currency=payment.currency if payment else None,
        payment_payee_id=payment.payee_id if payment else None,
        payment_payee_name=payment.payee_name if payment else None,
        payment_sender_balance=payment.sender_balance if payment else None,
        payment_note=payment.note if payment else None,
        payment_channel=payment.channel if payment else None,
        payment_merchant_category=payment.merchant_category if payment else None,
        result_json=result.model_dump(),
    )
    result.scan_id = row.id
    # Refresh stored payload with the final scan_id, label, and input echo so
    # history reads back identically. Extra keys are ignored by the response model.
    stored = result.model_dump()
    stored["scan_id"] = row.id
    stored["label"] = verdict["label"]
    stored["input_echo"] = verdict["input_echo"]
    row.result_json = stored
    db.commit()

    audit_service.append_entry(
        db,
        event_type="SCAN_SUBMITTED",
        entity_type="scan",
        entity_id=row.id,
        payload={
            "analysis_type": req.analysis_type,
            "risk_score": result.risk_score,
            "risk_level": result.risk_level,
            "pipeline_version": result.pipeline_version,
        },
        user_id=user_id,
    )

    # First sighting bookkeeping: link the qr_seen row to its first scan and
    # log exactly one QR_SEEN audit entry per payload hash (no chain spam).
    # Audit carries the hash prefix + class only — never payload material.
    if qr_first_sighting and qr_lookup_hash:
        from app.repositories import qr_seen as qr_seen_repo
        seen_row = qr_seen_repo.get_by_hash(db, qr_lookup_hash)
        if seen_row is not None:
            seen_row.first_scan_id = row.id
            db.commit()
        audit_service.append_entry(
            db,
            event_type="QR_SEEN",
            entity_type="qr",
            entity_id=qr_lookup_hash[:12],
            payload={
                "payload_hash_prefix": qr_lookup_hash[:12],
                "payload_class": result.evidence.payload_class,
                "first_scan_id": row.id,
            },
            user_id=user_id,
        )

    # Advisory stage (mandatory order): the deterministic verdict above is
    # fully built AND persisted before advisory runs. Advisory output attaches
    # to the response object only — it never modifies the persisted verdict.
    from app.services import advisory as advisory_service
    evidence_kinds = []
    if result.evidence.extracted_urls:
        evidence_kinds.append("urls")
    if result.evidence.matched_phrases:
        evidence_kinds.append("phrases")
    if result.evidence.qr_payload:
        evidence_kinds.append("qr_payload")
    if result.evidence.parsed_qr:
        evidence_kinds.append("parsed_qr")
    advisory_out = advisory_service.advise(
        enabled=settings.ADVISORY_ENABLED,
        provider_name=settings.ADVISORY_PROVIDER,
        endpoint=settings.ADVISORY_ENDPOINT,
        api_key=settings.ADVISORY_API_KEY,
        timeout_s=settings.ADVISORY_TIMEOUT_S,
        max_chars=settings.ADVISORY_MAX_CHARS,
        analysis_type=req.analysis_type,
        risk_level=result.risk_level,
        reasons=[r.model_dump() for r in result.reasons],
        seen_status=seen_status,
        evidence_kinds=evidence_kinds,
    )
    result.advisory = Advisory(**advisory_out)
    return result


@router.get("/categories")
def categories():
    return [
        {"label": label, **profile} for label, profile in CATEGORIES.items()
    ]
