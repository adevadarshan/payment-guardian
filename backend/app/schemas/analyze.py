# app/schemas/analyze.py — the full AnalysisResult contract (Slice 4).
# Additive-only: new optional fields get defaults so old rows still validate.

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.categories import ALLOWED_CATEGORIES


class StrictModel(BaseModel):
    """Base for request models: unknown fields are rejected, never dropped."""
    model_config = ConfigDict(extra="forbid")

PAYEE_ID_RE = r"^[A-Za-z0-9.\-_]{2,256}@[A-Za-z][A-Za-z0-9]{1,64}$"
RiskLevel = Literal["SAFE", "MEDIUM", "HIGH"]
AnalysisType = Literal["payment", "message", "url", "qr"]
SeenStatus = Literal["previously_seen", "new", "unable_to_verify", "not_applicable"]


class PaymentInput(StrictModel):
    amount: float = Field(..., gt=0, le=200000)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    payee_id: str = Field(..., min_length=1, pattern=PAYEE_ID_RE)
    payee_name: str = Field(default="Unknown", max_length=256)
    sender_balance: float = Field(..., gt=0)
    note: str | None = Field(default=None, max_length=280)
    channel: str = Field(default="upi", max_length=32)
    merchant_category: str

    @field_validator("merchant_category")
    @classmethod
    def _known_category(cls, v: str) -> str:
        if v not in ALLOWED_CATEGORIES:
            raise ValueError(f"Unknown merchant_category '{v}'")
        return v

    @field_validator("note")
    @classmethod
    def _clean_note(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = "".join(ch for ch in v.strip() if ch.isprintable())
        return cleaned or None


class MessageInput(StrictModel):
    text: str = Field(..., min_length=1, max_length=4000)
    context: Literal["sms", "whatsapp", "email", "unknown"] = "unknown"


class UrlInput(StrictModel):
    url: str = Field(..., min_length=1, max_length=2048)


class QrInput(StrictModel):
    image_base64: str | None = None  # raw upload, server-decoded (authority)
    payload: str | None = None       # client-decoded string (preview/convenience)


class PaymentContext(StrictModel):
    """Optional enrichment for message/url/qr analyses. Never with payment."""
    amount: float | None = Field(default=None, gt=0, le=200000)
    sender_balance: float | None = Field(default=None, gt=0)
    payee_name: str | None = Field(default=None, max_length=256)


class AnalyzeRequest(StrictModel):
    analysis_type: AnalysisType
    payment: PaymentInput | None = None
    message: MessageInput | None = None
    url: UrlInput | None = None
    qr: QrInput | None = None
    payment_context: PaymentContext | None = None
    # Advisory-only client-declared transaction time (Slice 2).
    # Production scoring NEVER uses this: the route supplies server-trusted
    # time unless ALLOW_CLIENT_HOUR is explicitly enabled (tests only).
    timestamp: str | None = None

    @model_validator(mode="after")
    def _exactly_matching_block(self) -> "AnalyzeRequest":
        blocks = {
            "payment": self.payment,
            "message": self.message,
            "url": self.url,
            "qr": self.qr,
        }
        present = [k for k, v in blocks.items() if v is not None]
        if present != [self.analysis_type]:
            raise ValueError(
                f"Exactly the '{self.analysis_type}' block must be present"
            )
        if self.analysis_type == "payment":
            if self.payment_context is not None:
                raise ValueError("payment_context is not allowed with analysis_type='payment'")
            if self.payment and self.payment.amount > self.payment.sender_balance:
                raise ValueError("amount must not exceed sender_balance")
        if self.analysis_type == "qr" and self.qr:
            if not self.qr.image_base64 and not self.qr.payload:
                raise ValueError("qr requires image_base64 or payload")
        return self


class Reason(BaseModel):
    code: str
    signal: str
    title: str
    observation: str
    impact: Literal["low", "medium", "high", "informational"]


class Signal(BaseModel):
    name: str
    source: Literal["rule", "ml", "advisory"]
    value: float | None = None
    weight: float | None = None
    contribution: float | None = None


class Evidence(BaseModel):
    extracted_urls: list[str] = []
    matched_phrases: list[str] = []
    qr_payload: str | None = None
    decoded: bool = False
    parsed_qr: dict = {}
    payload_class: str | None = None
    qr_decode: str = "none"  # none|client|server|both|failed


class SeenInfo(BaseModel):
    status: SeenStatus
    first_seen_at: str | None = None
    times_seen: int | None = None


class RecommendedAction(BaseModel):
    headline: str
    steps: list[str] = []


class Advisory(BaseModel):
    status: Literal["disabled", "ok", "timeout", "error"] = "disabled"
    provider: str | None = None
    text: str | None = None


class ModelInfo(BaseModel):
    backend: str = "none"
    version: str | None = None


class PaymentSummary(BaseModel):
    amount: float
    payee_id: str
    payee_name: str | None = None
    merchant_category: str
    channel: str
    sender_balance: float


class AnalysisResult(BaseModel):
    scan_id: str
    analysis_type: AnalysisType
    risk_score: int = Field(..., ge=0, le=100)
    risk_level: RiskLevel
    reasons: list[Reason]
    signals: list[Signal] = []
    evidence: Evidence = Evidence()
    seen: SeenInfo
    recommended_action: RecommendedAction
    advisory: Advisory = Advisory()
    model: ModelInfo = ModelInfo()
    pipeline_version: str
    created_at: str
    payment_summary: PaymentSummary | None = None


class ScanSummary(BaseModel):
    scan_id: str
    analysis_type: AnalysisType
    risk_score: int
    risk_level: RiskLevel
    label: str
    created_at: str

