# app/pipeline/normalize.py — pure input normalisation (Slice 3).
# No I/O, no clock, no randomness. Tables are explicit literals.

import hashlib
import re
import unicodedata
from urllib.parse import parse_qsl, urlsplit

# Leetspeak folding (applied after casefold).
# Digits fold ONLY when adjacent to a letter ("0tp" -> "otp", "bl0cked" ->
# "blocked") so numbers survive ("10 minutes", "Rs.5000", OTP codes).
# Non-digit symbols (@, $, +) always fold.
LEET_MAP: dict[str, str] = {
    "0": "o", "1": "l", "3": "e", "4": "a", "5": "s",
    "7": "t", "@": "a", "$": "s", "+": "t",
}

# Minimal confusable folding (Cyrillic/Greek look-alikes -> latin).
# Curated for scam-text evasion; not a general transliterator.
HOMOGLYPH_MAP: dict[str, str] = {
    "а": "a", "с": "c", "е": "e", "о": "o", "р": "p", "х": "x",
    "і": "i", "ј": "j", "ѕ": "s", "у": "y", "к": "k", "м": "m",
    "н": "h", "т": "t", "в": "b", "ο": "o", "ρ": "p", "ν": "v",
    "ԁ": "d",
}

TEXT_CAP = 4000
URL_CAP = 2048
QR_PAYLOAD_CAP = 8192
URL_EXTRACT_CAP = 10

_URL_TOKEN_RE = re.compile(r"(https?://[^\s\"'<>]+|www\.[^\s\"'<>]+)")


def _fold(mapping: dict[str, str], text: str) -> str:
    return "".join(mapping.get(ch, ch) for ch in text)


def _fold_leet(text: str) -> str:
    out: list[str] = []
    for i, ch in enumerate(text):
        sub = LEET_MAP.get(ch)
        if sub is None:
            out.append(ch)
            continue
        if ch.isdigit():
            prev = text[i - 1] if i > 0 else ""
            nxt = text[i + 1] if i + 1 < len(text) else ""
            if not (prev.isalpha() or nxt.isalpha()):
                out.append(ch)
                continue
        out.append(sub)
    return "".join(out)


def normalize_text(s: str, *, cap: int = TEXT_CAP) -> tuple[str, bool]:
    """Normalize free text. Returns (normalized, was_truncated)."""
    text = unicodedata.normalize("NFKC", s.strip()).casefold()
    text = _fold_leet(text)
    text = _fold(HOMOGLYPH_MAP, text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > cap:
        return text[:cap], True
    return text, False


def extract_urls(text: str, *, cap: int = URL_EXTRACT_CAP) -> list[str]:
    """Syntactic URL token extraction. No fetching, no validation."""
    seen: list[str] = []
    for match in _URL_TOKEN_RE.finditer(text):
        token = match.group(1).rstrip(".,;:!?)")
        if token not in seen:
            seen.append(token)
        if len(seen) >= cap:
            break
    return seen


def normalize_url(raw: str, *, cap: int = URL_CAP) -> dict:
    """Parse a URL into parts. Raises ValueError when unusable."""
    raw = raw.strip()
    if not raw or len(raw) > cap:
        raise ValueError("URL is empty or too long")
    candidate = raw if "://" in raw else f"http://{raw}"
    try:
        parts = urlsplit(candidate)
    except ValueError as exc:
        raise ValueError(f"URL is unparseable: {exc}") from exc
    if not parts.hostname:
        raise ValueError("URL has no host")
    host = parts.hostname.lower()
    port = parts.port
    if (parts.scheme == "http" and port == 80) or (parts.scheme == "https" and port == 443):
        port = None
    return {
        "scheme": parts.scheme.lower(),
        "host": host,
        "port": port,
        "has_credentials": parts.username is not None,
        "path": parts.path or "/",
        "query": parts.query or "",
        "raw": raw[:cap],
    }


def normalize_qr_payload(raw: str, *, cap: int = QR_PAYLOAD_CAP) -> str:
    """Normalize a decoded QR payload string."""
    text = unicodedata.normalize("NFKC", raw).strip()
    return text[:cap]


def qr_payload_hash(normalized: str) -> str:
    """Stable hash: UPI payloads hash with query params sorted by key."""
    material = normalized
    if normalized[:6].lower() == "upi://":
        try:
            _, _, rest = normalized.partition("?")
            params = sorted(parse_qsl(rest, keep_blank_values=True))
            material = normalized.split("?", 1)[0].lower() + "?" + "&".join(f"{k}={v}" for k, v in params)
        except Exception:
            material = normalized
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
