# app/analyzers/qr_analyzer.py — QR decode, classification, UPI parsing,
# and routing into the URL/message/payment signal paths (Slice 3).
# No network, no clock, no randomness.
#
# Decoder availability rule: OpenCV is imported at module load, so a missing
# library fails loudly at application startup. A malformed or unreadable QR
# image at request time is a routine unable_to_verify outcome. The two are
# never conflated.
import re
from urllib.parse import parse_qsl, urlsplit

import cv2
import numpy as np

from app.pipeline import normalize as nz
from app.pipeline import rules
from app.pipeline.signals import Signal
from app.schemas.analyze import PAYEE_ID_RE

_DETECTOR = cv2.QRCodeDetector()

MAGIC = (
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpeg"),
    (b"GIF8", "gif"),
)
WEBP_MAGIC = (b"RIFF", b"WEBP")


class DecodeError(Exception):
    """Raised for oversized / wrong-type / undecodable uploads."""


def sniff_format(raw: bytes) -> str | None:
    """Magic-byte sniff. Client MIME is never trusted."""
    for magic, name in MAGIC:
        if raw.startswith(magic):
            return name
    if raw.startswith(WEBP_MAGIC[0]) and WEBP_MAGIC[1] in raw[8:16]:
        return "webp"
    return None

UPI_FIELDS = ("pa", "pn", "am", "cu", "tr", "tn", "mc", "rpayee")

_CONTACT_RES = (
    re.compile(r"^\s*BEGIN:VCARD", re.IGNORECASE),
    re.compile(r"^\s*(tel|sms|smsto|mailto):", re.IGNORECASE),
)
_CRYPTO_RES = (
    re.compile(r"^\s*bitcoin:", re.IGNORECASE),
    re.compile(r"^\s*ethereum:", re.IGNORECASE),
    re.compile(r"^\s*bc1[qp][a-z0-9]{6,}", re.IGNORECASE),
    re.compile(r"^\s*0x[0-9a-fA-F]{40}\s*$"),
)


def decode_image(raw: bytes, *, max_bytes: int, max_megapixels: int) -> str:
    """Decode a QR image to its payload string (server authority).

    Raises DecodeError("too_large") / ("unsupported_media") / ("undecodable").
    Any other outcome is a bug, not a verdict input.
    """
    if len(raw) > max_bytes:
        raise DecodeError("too_large")
    if sniff_format(raw) is None:
        raise DecodeError("unsupported_media")
    try:
        arr = np.frombuffer(raw, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception as exc:
        raise DecodeError("undecodable") from exc
    if img is None:
        raise DecodeError("undecodable")
    height, width = img.shape[:2]
    if width * height > max_megapixels * 1_000_000:
        raise DecodeError("too_large")
    try:
        payload, _, _ = _DETECTOR.detectAndDecode(img)
    except Exception as exc:
        raise DecodeError("undecodable") from exc
    if not payload:
        raise DecodeError("undecodable")
    return payload


def classify_payload(payload: str) -> str:
    """Ordered predicates, first match wins. Returns the payload class."""
    text = payload.strip()
    if not text:
        return "unknown"
    lowered = text[:8].lower()
    if lowered.startswith("upi://"):
        return "upi_uri"
    if re.match(r"^https?://", text, re.IGNORECASE):
        return "url"
    if any(rx.match(text) for rx in _CONTACT_RES):
        return "contact"
    if any(rx.match(text) for rx in _CRYPTO_RES):
        return "crypto"
    if not re.search(r"[A-Za-z0-9]", text):
        return "unknown"
    return "text"


def extract_upi(payload: str) -> dict:
    """Parse upi://pay?... into the 8 UPI fields. Missing -> None."""
    out: dict[str, str | float | None] = {key: None for key in UPI_FIELDS}
    try:
        query = urlsplit(payload.strip()).query
    except ValueError:
        return out
    for key, value in parse_qsl(query, keep_blank_values=True):
        k = key.lower()
        if k in out and out[k] is None:
            out[k] = (value or "")[:256] or None
    raw_amount = out.get("am")
    if isinstance(raw_amount, str):
        try:
            out["am"] = float(raw_amount)
        except ValueError:
            out["am"] = None
    return out


def _impact(points: int) -> str:
    if points >= 20:
        return "high"
    if points >= 10:
        return "medium"
    return "low"


def _tokens(text: str) -> set[str]:
    return set(t for t in re.findall(r"[a-z0-9]+", text.lower()) if t)


def analyze_qr_payload(payload: str, *, payment_context=None) -> tuple[list[Signal], list[str], dict]:
    """Score a decoded QR payload string.

    Returns (signals, matched_phrases, parsed_qr). routed_* reasons come from
    the shared URL/message analyzers so cross-type composition is uniform.
    """
    from app.analyzers import message_analyzer, url_analyzer

    normalized = nz.normalize_qr_payload(payload)
    payload_class = classify_payload(normalized)
    signals: list[Signal] = []
    matched: list[str] = []
    parsed: dict = {}

    def fire(name: str, points: int, observation: str, title: str,
             value: float | None = None) -> None:
        signals.append(Signal(name=name, value=value, contribution=points,
                              observation=observation, title=title,
                              impact=_impact(points)))

    if payload_class == "url":
        sub, sub_matched = url_analyzer.analyze_url(normalized)
        signals.extend(sub)
        matched.extend(sub_matched)
    elif payload_class == "text":
        sub, sub_matched, _ = message_analyzer.analyze_message(normalized)
        signals.extend(sub)
        matched.extend(sub_matched)
    elif payload_class == "contact":
        fire("qr.contact_payload", 10,
             "QR encodes a contact handover (call/SMS/mail target)",
             "Contact handover in QR")
    elif payload_class == "crypto":
        fire("qr.crypto_payload", 20,
             "QR encodes a crypto payment address",
             "Crypto address in QR")
    elif payload_class == "upi_uri":
        parsed = extract_upi(normalized)
        amount = parsed.get("am")
        if isinstance(amount, (int, float)) and amount > 0:
            tier_points, tier_label = rules.amount_tier(float(amount))
            if tier_points:
                fire("payment.amount_tier", tier_points,
                     f"QR amount Rs.{amount:g} crosses the {tier_label} tier",
                     "Large amount in QR", float(amount))
            floor = rules.magnitude_floor(float(amount))
            if floor >= 50:
                fire("payment.amount_magnitude", 20,
                     f"QR amount Rs.{amount:g} approaches the Rs.200,000 limit",
                     "QR amount near the UPI limit", float(amount))
        payee = parsed.get("pa")
        if isinstance(payee, str) and not re.match(PAYEE_ID_RE, payee):
            fire("qr.upi_bad_payee", 15,
                 f"QR payee id is malformed: {payee[:64]}",
                 "Malformed UPI payee")
        name = parsed.get("pn")
        if isinstance(payee, str) and isinstance(name, str) and name.strip():
            local = payee.split("@", 1)[0]
            if _tokens(name).isdisjoint(_tokens(local)):
                fire("qr.merchant_mismatch", 15,
                     f"QR merchant name '{name[:64]}' does not match payee '{local[:64]}'",
                     "Merchant/payee mismatch")
        if (isinstance(amount, (int, float)) and payment_context is not None
                and payment_context.amount is not None
                and abs(float(amount) - float(payment_context.amount)) > 0.01):
            fire("qr.amount_conflict", 20,
                 f"QR amount Rs.{amount:g} differs from the stated Rs.{payment_context.amount:g}",
                 "QR amount conflict")
    else:  # unknown
        fire("qr.unclassified", 5,
             "QR payload could not be classified",
             "Unclassified QR payload")

    return signals, sorted(set(matched)), {"class": payload_class, "parsed": parsed}


class QrAnalyzer:
    name = "qr"

    def matches(self, analysis_type: str) -> bool:
        return analysis_type == "qr"

    def analyze(self, normalized: object, ctx: dict) -> list[Signal]:
        signals, _, _ = analyze_qr_payload(
            str(normalized), payment_context=ctx.get("payment_context"))
        return signals
