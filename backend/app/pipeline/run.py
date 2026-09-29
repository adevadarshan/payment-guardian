# app/pipeline/run.py — single orchestration entry (Slice 4).
# Payment path uses the Slice 2 computation order exactly (per the §3.1
# identity), with an optional bounded ML signal fused into the additive base.
# Message/url compose analyzer signals through fuse/explain.
from app.analyzers import message_analyzer, ml_analyzer, qr_analyzer, url_analyzer
from app.analyzers.payment_analyzer import (
    collect_payment_signals,
    finish_payment_verdict,
    payment_context_signals,
)
from app.config import settings
from app.ml import registry as ml_registry
from app.pipeline import explain, normalize as nz
from app.pipeline.fuse import fuse
from app.pipeline.signals import Signal


def _summarize(signals: list[Signal], *, analysis_type: str,
               seen_status: str = "not_applicable") -> dict:
    ordered = explain.order_signals(signals)
    score = fuse(signals)
    level = explain.level_for(score)
    action = explain.select_action(level, analysis_type, seen_status=seen_status)
    return {
        "risk_score": score,
        "risk_level": level,
        "reasons": [s.to_reason() for s in ordered],
        "signals": [s.to_dict() for s in ordered],
        "recommended_action": action,
    }


def _context_echo(payment_context) -> dict | None:
    return payment_context.model_dump() if payment_context else None


def analyze_request(*, analysis_type: str, payment=None, message=None,
                    url=None, qr=None, payment_context=None, hour=None,
                    image_bytes: bytes | None = None,
                    qr_limits: dict | None = None,
                    store_qr_payload: bool = True) -> dict:
    """Run one analysis. Returns verdict parts + label + input_echo + evidence extras."""
    if analysis_type == "payment":
        assert payment is not None
        pre, post, aux = collect_payment_signals(payment, hour=hour)
        handle = ml_registry.get(settings.MODEL_BACKEND)
        ml_sig = ml_analyzer.ml_signal(payment, hour=hour, handle=handle)
        if ml_sig is not None:
            pre.append(ml_sig)  # fused with the additive base; ceilings dominate
        verdict = finish_payment_verdict(pre, post, aux)
        label = f"Rs.{payment.amount:g} to {payment.payee_id}"
        echo = {"input_text": None, "input_url": None,
                "input_qr_payload_hash": None, "payment_context": None}
        model = {"backend": settings.MODEL_BACKEND,
                 "version": handle.version if handle else None}
        return {**verdict, "label": label, "input_echo": echo,
                "seen_status": "not_applicable", "extra_evidence": {},
                "model": model}

    signals: list[Signal] = []
    matched: list[str] = []
    urls: list[str] = []

    if analysis_type == "message":
        assert message is not None
        m_signals, m_matched, m_urls = message_analyzer.analyze_message(
            message.text, context=message.context)
        signals.extend(m_signals)
        matched.extend(m_matched)
        for link in m_urls:
            try:
                u_signals, _ = url_analyzer.analyze_url(link)
            except ValueError:
                continue
            signals.extend(u_signals)
            urls.append(link)
        stripped = message.text.strip()
        label = (stripped[:40] + "…") if len(stripped) > 40 else stripped
        echo = {"input_text": message.text[:4000], "input_url": None,
                "input_qr_payload_hash": None,
                "payment_context": _context_echo(payment_context)}
    elif analysis_type == "url":
        assert url is not None
        u_signals, u_matched = url_analyzer.analyze_url(url.url)
        signals.extend(u_signals)
        matched.extend(u_matched)
        urls.append(url.url)
        host = url.url.split("://", 1)[-1].split("/", 1)[0][:60]
        label = f"Link: {host}"
        echo = {"input_text": None, "input_url": url.url[:2048],
                "input_qr_payload_hash": None,
                "payment_context": _context_echo(payment_context)}
    elif analysis_type == "qr":
        # Server decode is authoritative: when image bytes are present the
        # client payload is ignored. Payload-only requests use the string.
        assert qr is not None
        from app.analyzers.qr_analyzer import DecodeError
        decode_source = "client"
        decoded_ok = True
        payload_text = qr.payload or ""
        if image_bytes is not None:
            limits = qr_limits or {}
            try:
                payload_text = qr_analyzer.decode_image(
                    image_bytes,
                    max_bytes=limits.get("max_bytes", 5 * 1024 * 1024),
                    max_megapixels=limits.get("max_megapixels", 12),
                )
                decode_source = "both" if qr.payload and qr.payload.strip() == payload_text.strip() else "server"
            except DecodeError as exc:
                if str(exc) in ("too_large", "unsupported_media"):
                    raise  # route maps to 413/422; only undecodable degrades
                decoded_ok = False
                decode_source = "failed"
        if not decoded_ok or not payload_text.strip():
            unverifiable = [Signal(
                name="qr.unverifiable", contribution=0,
                observation="The QR image could not be decoded",
                title="Unreadable QR code", impact="informational", rank=9)]
            out = _summarize(unverifiable, analysis_type=analysis_type,
                             seen_status="unable_to_verify")
            out["evidence"] = explain.build_evidence(decoded=False, qr_decode=decode_source)
            out["label"] = "QR undecodable"
            out["input_echo"] = {
                "input_text": None, "input_url": None,
                "input_qr_payload_hash": None,
                "payment_context": _context_echo(payment_context)}
            out["seen_status"] = "unable_to_verify"
            out["extra_evidence"] = {}
            return out
        q_signals, q_matched, q_info = qr_analyzer.analyze_qr_payload(
            payload_text, payment_context=payment_context)
        signals.extend(q_signals)
        matched.extend(q_matched)
        payload_class = q_info["class"]
        parsed = q_info["parsed"]
        normalized_full = nz.normalize_qr_payload(payload_text)
        preview = normalized_full[:40]
        label = f"QR {payload_class}: {preview}" if preview else "QR undecodable"
        echo = {"input_text": None, "input_url": None,
                "input_qr_payload_hash": None,  # filled by seen service (increment 8)
                "payment_context": _context_echo(payment_context)}
        if payment_context is not None:
            signals.extend(payment_context_signals(payment_context))
        out = _summarize(signals, analysis_type=analysis_type)
        out["evidence"] = explain.build_evidence(
            extracted_urls=urls, matched_phrases=matched,
            qr_payload=(payload_text[:8192] if store_qr_payload else None),
            decoded=True, parsed_qr=parsed, payload_class=payload_class,
            qr_decode=decode_source)
        out["label"] = label
        out["input_echo"] = echo
        # Seen detection runs in the route (it needs the DB + scan id).
        # The lookup key travels here so the route stays free of hashing logic.
        from app.pipeline.normalize import qr_payload_hash
        out["qr_lookup"] = {
            "payload_hash": qr_payload_hash(normalized_full),
            "payload_class": payload_class,
            "preview": normalized_full[:120],
        }
        out["seen_status"] = "not_applicable"  # replaced by the route after lookup
        out["extra_evidence"] = {}
        return out
    else:
        raise ValueError(f"Unsupported analysis_type '{analysis_type}'")

    if payment_context is not None:
        signals.extend(payment_context_signals(payment_context))

    out = _summarize(signals, analysis_type=analysis_type)
    out["evidence"] = explain.build_evidence(
        extracted_urls=urls, matched_phrases=matched)
    out["label"] = label
    out["input_echo"] = echo
    out["seen_status"] = "not_applicable"
    out["extra_evidence"] = {}
    return out
