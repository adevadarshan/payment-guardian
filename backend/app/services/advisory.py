# app/services/advisory.py — optional narrative guidance (Slice 4).
# Advisory is NEVER part of the verdict: it runs after the deterministic
# verdict is built AND persisted, and its output attaches to the response
# object only. A timeout/error degrades to a status, never to a 500, and
# never modifies score, level, reasons, or signals.
#
# Privacy rule: providers receive ONLY redacted summaries (level, reason
# codes + static titles, seen status, evidence kinds). Raw message text,
# URLs, QR payloads, names, and amounts never leave this process unless a
# human explicitly approves otherwise (no such approval exists).
import json
import logging
import urllib.request
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Protocol

logger = logging.getLogger("vh-s02")


class Provider(Protocol):
    name: str

    def generate(self, redacted: dict, *, timeout_s: int) -> str: ...


def redact_input(*, analysis_type: str, risk_level: str, reasons: list,
                 seen_status: str, evidence_kinds: list[str]) -> dict:
    """Build the provider input. Static titles only — no observations,
    no matched phrases, no amounts, no identifiers."""
    return {
        "analysis_type": analysis_type,
        "risk_level": risk_level,
        "signals": [
            {"code": r.get("code", ""), "title": r.get("title", ""),
             "impact": r.get("impact", "")}
            for r in reasons
        ],
        "seen_status": seen_status,
        "evidence_kinds": sorted(set(evidence_kinds)),
    }


class StubProvider:
    """Deterministic offline guidance assembled from the verdict. Default."""
    name = "stub"

    def generate(self, redacted: dict, *, timeout_s: int) -> str:
        level = redacted.get("risk_level", "SAFE")
        signals = redacted.get("signals", []) or []
        top = signals[0].get("title", "unusual patterns") if signals else "no specific signals"
        n = len(signals)
        if level == "HIGH":
            advice = (f"This check found {n} risk signal(s), led by {top}. "
                      f"Do not proceed with any payment or sharing of codes. "
                      f"Verify through a channel you already trust.")
        elif level == "MEDIUM":
            advice = (f"This check found {n} risk signal(s), led by {top}. "
                      f"Pause and verify the other party through a trusted channel "
                      f"before proceeding.")
        else:
            advice = ("Nothing in this check stood out. If anything still feels "
                      "off, verify through a channel you already trust.")
        return advice


class HttpProvider:
    """Generic OpenAI-compatible endpoint. Opt-in only (env-configured)."""

    def __init__(self, endpoint: str, api_key: str):
        self._endpoint = endpoint
        self._api_key = api_key

    @property
    def name(self) -> str:
        try:
            from urllib.parse import urlsplit
            return urlsplit(self._endpoint).hostname or "http"
        except Exception:
            return "http"

    def generate(self, redacted: dict, *, timeout_s: int) -> str:
        body = json.dumps({"input": redacted}).encode("utf-8")
        request = urllib.request.Request(
            self._endpoint, data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self._api_key}"},
            method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                payload = json.loads(response.read(4096).decode("utf-8", "replace"))
        except Exception as exc:
            raise AdvisoryError(f"provider request failed: {exc}") from exc
        text = payload.get("text") if isinstance(payload, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise AdvisoryError("provider returned no usable text")
        return text


class AdvisoryError(Exception):
    pass


def _run_with_timeout(provider: Provider, redacted: dict, timeout_s: int) -> str:
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(provider.generate, redacted, timeout_s=timeout_s)
        try:
            return future.result(timeout=timeout_s)
        except FutureTimeout as exc:
            raise AdvisoryError(f"provider timed out after {timeout_s}s") from exc


def advise(*, enabled: bool, provider_name: str, endpoint: str | None,
           api_key: str | None, timeout_s: int, max_chars: int,
           analysis_type: str, risk_level: str, reasons: list,
           seen_status: str, evidence_kinds: list[str]) -> dict:
    """Build the advisory response object. Never raises, never mutates input."""
    if not enabled:
        return {"status": "disabled", "provider": None, "text": None}
    redacted = redact_input(
        analysis_type=analysis_type, risk_level=risk_level, reasons=reasons,
        seen_status=seen_status, evidence_kinds=evidence_kinds)
    try:
        if provider_name == "http":
            if not endpoint or not api_key:
                raise AdvisoryError("HTTP provider selected but endpoint/key missing")
            provider: Provider = HttpProvider(endpoint, api_key)
        else:
            provider = StubProvider()
        text = _run_with_timeout(provider, redacted, timeout_s)
    except AdvisoryError as exc:
        logger.error("Advisory failed (%s); continuing without guidance", exc)
        return {"status": "error" if "timed out" not in str(exc) else "timeout",
                "provider": provider_name if provider_name == "http" else "stub",
                "text": None}
    except Exception as exc:  # never break analysis for narrative text
        logger.error("Advisory failed unexpectedly; continuing: %s", exc)
        return {"status": "error", "provider": "stub", "text": None}
    return {"status": "ok", "provider": provider.name, "text": text[:max_chars]}
