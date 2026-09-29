# app/db/models.py — Slice 1 tables + Slice 3 qr_seen.
# users arrive in Slice 4 via a later migration.

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    analysis_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    pipeline_version: Mapped[str] = mapped_column(String(32), nullable=False)
    # Payment input — every accepted field is stored (no silent drops).
    payment_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    payment_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    payment_payee_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_payee_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_sender_balance: Mapped[float | None] = mapped_column(Float, nullable=True)
    payment_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_channel: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payment_merchant_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at_str: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )


class QrSeen(Base):
    """Previously-seen QR payloads, keyed by normalized-payload hash (Slice 3)."""

    __tablename__ = "qr_seen"
    __table_args__ = (CheckConstraint("times_seen >= 1", name="ck_qr_seen_times_seen"),)

    payload_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload_class: Mapped[str] = mapped_column(String(16), nullable=False)
    normalized_preview: Mapped[str] = mapped_column(String(280), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    times_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_scan_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("scans.id", ondelete="SET NULL"), nullable=True
    )

class User(Base):
    """Application users (Slice 4). Passwords are Argon2id hashes, never plaintext."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Session(Base):
    """Opaque bearer sessions. Tokens are SHA-256 hashed at rest (Slice 4)."""

    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # access|refresh
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
