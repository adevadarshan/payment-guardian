# scripts/seed.py — idempotent demo seeding (Slice 4).
# Usage from backend/:  DATABASE_URL=... python scripts/seed.py
# Creates env-seeded demo users + a small mixed scan history via the API
# layer (repositories + analyzers, no HTTP needed). Safe to re-run.
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.models import User  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.pipeline import run as pipeline  # noqa: E402
from app.repositories import scans as scan_repo  # noqa: E402
from app.schemas.analyze import MessageInput, PaymentInput, UrlInput  # noqa: E402
from app.security import auth as auth_service  # noqa: E402
from app.services import audit_service  # noqa: E402

Base.metadata.create_all(bind=engine)

DEMOS = [
    ("demo@vhs02.local", os.environ.get("DEMO_PASSWORD", settings.DEMO_PASSWORD), "Demo"),
    ("analyst@vhs02.local", "analyst1234", "Analyst"),
]

PAYMENTS = [
    {"amount": 150.0, "currency": "INR", "payee_id": "shop@grocery",
     "payee_name": "Corner Shop", "sender_balance": 5000.0, "note": "groceries",
     "channel": "upi", "merchant_category": "Groceries"},
    {"amount": 3500.0, "currency": "INR", "payee_id": "vendor@upi",
     "payee_name": "Vendor", "sender_balance": 20000.0, "note": "headphones",
     "channel": "upi", "merchant_category": "Electronics"},
    {"amount": 12000.0, "currency": "INR", "payee_id": "unknown@upi",
     "payee_name": "Unknown", "sender_balance": 50000.0, "note": None,
     "channel": "upi", "merchant_category": "Travel"},
]


def main() -> None:
    db = SessionLocal()
    try:
        users = []
        for email, password, display in DEMOS:
            user = db.query(User).filter(User.email == email).first()
            if user is None:
                user = User(email=email, password_hash=auth_service.hash_password(password),
                            display_name=display, is_demo=True)
                db.add(user)
                db.commit()
                db.refresh(user)
                print(f"created user {email}")
            users.append(user)
        owner = users[0]
        if db.query(scan_repo.Scan).count() == 0:
            for payload in PAYMENTS:
                verdict = pipeline.analyze_request(
                    analysis_type="payment",
                    payment=PaymentInput(**payload), hour=14)
                row = scan_repo.create_scan(
                    db, user_id=owner.id, analysis_type="payment",
                    risk_score=verdict["risk_score"], risk_level=verdict["risk_level"],
                    pipeline_version=settings.PIPELINE_VERSION,
                    payment_amount=payload["amount"], payment_currency="INR",
                    payment_payee_id=payload["payee_id"], payment_payee_name=payload["payee_name"],
                    payment_sender_balance=payload["sender_balance"], payment_note=payload["note"],
                    payment_channel="upi", payment_merchant_category=payload["merchant_category"],
                    result_json={**verdict_to_json(verdict), "scan_id": "seeded"})
                audit_service.append_entry(
                    db, event_type="SCAN_SUBMITTED", entity_type="scan",
                    entity_id=row.id,
                    payload={"analysis_type": "payment", "risk_score": row.risk_score,
                             "risk_level": row.risk_level,
                             "pipeline_version": row.pipeline_version},
                    user_id=owner.id)
            # One message + one URL scan for type coverage.
            for analysis_type, kwargs in (
                ("message", {"message": MessageInput(text="Your EMI of Rs.4,500 is debited.")}),
                ("url", {"url": UrlInput(url="https://www.hdfcbank.com/")}),
            ):
                verdict = pipeline.analyze_request(analysis_type=analysis_type, **kwargs)
                row = scan_repo.create_scan(
                    db, user_id=owner.id, analysis_type=analysis_type,
                    risk_score=verdict["risk_score"], risk_level=verdict["risk_level"],
                    pipeline_version=settings.PIPELINE_VERSION, result_json={})
                stored = dict(verdict_to_json(verdict))
                stored["scan_id"] = row.id
                row.result_json = stored
                db.commit()
                audit_service.append_entry(
                    db, event_type="SCAN_SUBMITTED", entity_type="scan",
                    entity_id=row.id,
                    payload={"analysis_type": analysis_type,
                             "risk_score": row.risk_score, "risk_level": row.risk_level,
                             "pipeline_version": row.pipeline_version},
                    user_id=owner.id)
            print("seeded scan history")
        else:
            print("scans already present; skipping history seed")
    finally:
        db.close()


def verdict_to_json(verdict: dict) -> dict:
    return {
        "analysis_type": "payment",
        "risk_score": verdict["risk_score"],
        "risk_level": verdict["risk_level"],
        "reasons": verdict["reasons"],
        "signals": verdict["signals"],
        "evidence": verdict["evidence"],
        "seen": {"status": "not_applicable", "first_seen_at": None, "times_seen": None},
        "recommended_action": verdict["recommended_action"],
        "advisory": {"status": "disabled", "provider": None, "text": None},
        "model": {"backend": settings.MODEL_BACKEND, "version": None},
        "pipeline_version": settings.PIPELINE_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "payment_summary": None,
    }


if __name__ == "__main__":
    main()
