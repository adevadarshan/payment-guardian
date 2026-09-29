# app/logging_redact.py — log redaction for sensitive values (Slice 4).
# Allowlist approach in reverse: known-sensitive keys are masked wherever
# they appear in formatted log records. Structured request logging elsewhere
# in the app must use allowlisted fields only (see tests).
import logging
import re

# Keys whose values must never appear in logs (case-insensitive).
SENSITIVE_KEYS = (
    "password", "passwd", "pwd", "token", "secret", "api_key", "apikey",
    "authorization", "qr_payload", "image_base64", "message_text",
    "input_text", "input_url", "payload",
)

_PAIR = re.compile(
    r"(?i)(['\"]?(?:%s)['\"]?\s*[:=]\s*)(?:\"([^\"]*)\"|'([^']*)'|([^\s,}]+))"
    % "|".join(SENSITIVE_KEYS)
)
_BEARER_PATTERN = re.compile(r"(?i)\b(bearer\s+)([A-Za-z0-9\-._~+/=]+)")


def redact(text: str) -> str:
    """Mask sensitive key=value pairs and bearer tokens in a log string."""
    # Bearer first: otherwise the generic key=value rule eats the word
    # "Bearer" as the value and leaves the token behind.
    redacted = _BEARER_PATTERN.sub(lambda m: f"{m.group(1)}***REDACTED***", text)
    return _PAIR.sub(lambda m: f"{m.group(1)}***REDACTED***", redacted)


class RedactingFilter(logging.Filter):
    """Attach to handlers so no log record can leak sensitive values."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True
        masked = redact(message)
        record.msg = masked
        record.args = ()
        return True


def install() -> None:
    """Attach the redacting filter to the root logger handlers."""
    root = logging.getLogger()
    filt = RedactingFilter()
    for handler in root.handlers:
        handler.addFilter(filt)
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.addFilter(filt)
        root.addHandler(handler)
