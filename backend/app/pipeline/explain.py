# app/pipeline/explain.py — reasons ordering, evidence, safe actions (Slice 3).
# Pure functions. Wording lives in analyzers; this module orders and bundles.
from app.pipeline.signals import Signal
from app.pipeline.thresholds import classify

SAFE_ACTION = {
    "headline": "Transaction appears legitimate. Proceed normally.",
    "steps": [
        "If anything about this request feels off, confirm the payee through a channel you already trust."
    ],
}
MEDIUM_ACTION = {
    "headline": "Unusual patterns detected. Request additional verification.",
    "steps": [
        "Pause before paying.",
        "Confirm the payee name and UPI ID with the recipient directly — not through any link or number in this request.",
        "Check that the amount matches what you agreed.",
    ],
}
HIGH_ACTION = {
    "headline": "Potential fraud detected. Block transaction & alert user.",
    "steps": [
        "Do not pay.",
        "Never share an OTP, PIN, or CVV — no legitimate payment asks for one.",
        "If you already paid, contact your bank immediately.",
    ],
}

TYPE_STEPS: dict[str, dict[str, list[str]]] = {
    "message": {
        "MEDIUM": ["Do not reply, call back, or click anything in the message. Contact the organisation through a number you already trust."],
        "HIGH": ["Do not reply, call back, or click anything in the message. Contact the organisation through a number you already trust."],
    },
    "url": {
        "MEDIUM": ["Do not enter passwords, OTPs, or payment details on this page. If you already did, change that password and alert your bank."],
        "HIGH": ["Do not enter passwords, OTPs, or payment details on this page. If you already did, change that password and alert your bank."],
    },
    "qr": {
        "SAFE": ["This code is new to us — that is not a safety signal. Anyone can generate a QR. Verify the recipient out-of-band before paying."],
        "MEDIUM": ["This code is new to us — that is not a safety signal. Anyone can generate a QR. Verify the recipient out-of-band before paying."],
        "HIGH": ["This code is new to us — that is not a safety signal. Anyone can generate a QR. Verify the recipient out-of-band before paying."],
    },
}


def order_signals(signals: list[Signal]) -> list[Signal]:
    """Contribution desc; ties broken by rank, then name.

    Zero-contribution signals are skipped, except informational ones
    (e.g. qr.unverifiable, qr.seen_new): their presence IS the message.
    """
    firing = [s for s in signals if s.contribution != 0 or s.impact == "informational"]
    return sorted(firing, key=lambda s: (-s.contribution, s.rank, s.name))


def build_evidence(
    *,
    extracted_urls: list[str] | None = None,
    matched_phrases: list[str] | None = None,
    qr_payload: str | None = None,
    decoded: bool = False,
    parsed_qr: dict | None = None,
    payload_class: str | None = None,
    qr_decode: str = "none",
) -> dict:
    return {
        "extracted_urls": list((extracted_urls or [])[:10]),
        "matched_phrases": sorted(set(matched_phrases or []))[:20],
        "qr_payload": qr_payload,
        "decoded": decoded,
        "parsed_qr": parsed_qr or {},
        "payload_class": payload_class,
        "qr_decode": qr_decode,
    }


def select_action(level: str, analysis_type: str, *, seen_status: str = "not_applicable") -> dict:
    base = SAFE_ACTION if level == "SAFE" else MEDIUM_ACTION if level == "MEDIUM" else HIGH_ACTION
    steps = list(base["steps"])
    extra = TYPE_STEPS.get(analysis_type, {}).get(level, [])
    if analysis_type == "qr" and seen_status != "new":
        extra = []  # the new-code warning applies to first sightings only
    steps.extend(extra)
    if analysis_type == "qr" and seen_status == "unable_to_verify":
        action = base if level != "SAFE" else MEDIUM_ACTION
        return {
            "headline": action["headline"],
            "steps": list(action["steps"]) + [
                "We could not read this code. Do not scan it again elsewhere — verify the recipient another way."
            ],
        }
    return {"headline": base["headline"], "steps": steps}


def level_for(score: int) -> str:
    return classify(score)


def seen_reason(status: str, *, first_seen_at=None, times_seen: int | None = None) -> dict | None:
    """Informational seen-status reason. NEW≠SAFE is stated in the copy itself."""
    if status == "new":
        return {
            "code": "qr.seen_new",
            "signal": "qr.seen",
            "title": "First time seen",
            "observation": "First time seen — a new code is not a verified-safe code",
            "impact": "informational",
        }
    if status == "previously_seen":
        return {
            "code": "qr.seen_before",
            "signal": "qr.seen",
            "title": "Previously seen",
            "observation": (
                f"Seen before — first scanned {first_seen_at}, {times_seen} time(s). "
                "Repeated sightings are common for legitimate merchant codes."
            ),
            "impact": "informational",
        }
    return None
