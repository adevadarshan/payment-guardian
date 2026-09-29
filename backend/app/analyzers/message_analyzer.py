# app/analyzers/message_analyzer.py — deterministic scam-text signals (Slice 3).
# Pure functions of normalized text. No network, no clock, no randomness.
# Benign informational messages (e.g. OTP delivery notices) stay quiet:
# only disclosure-request + pressure patterns move the score.

import re

from app.pipeline import normalize as nz
from app.pipeline.signals import Signal

# Keyword families: (code suffix, points, phrases). Word-boundary matched
# on normalized text. Cross-family compounding is itself a scam marker;
# total keyword contribution is capped.
KEYWORD_FAMILIES: tuple[tuple[str, int, frozenset[str]], ...] = (
    ("urgency", 25, frozenset({
        "urgent", "urgently", "immediately", "act now", "expires", "expire",
        "last chance", "hurry", "at once", "right away",
    })),
    ("credential", 25, frozenset({
        "otp", "pin", "cvv", "password", "kyc", "verify", "verification",
        "account number", "card number", "aadhaar", "code",
    })),
    ("incentive", 20, frozenset({
        "lottery", "prize", "won", "winner", "reward", "cashback",
        "refund", "claim", "gift", "bonus", "congratulations",
    })),
    ("pressure", 25, frozenset({
        "pay now", "pay within", "today only", "blocked", "suspended", "frozen",
        "deactivated", "account will be", "locked", "fee", "tax", "charges",
        "processing fee",
    })),
    ("threat", 25, frozenset({
        "police", "court", "legal", "arrest", "fraud department", "rbi",
        "cbi", "cyber cell",
    })),
    ("gift_crypto", 20, frozenset({
        "gift card", "google play", "itunes", "crypto", "usdt",
        "bitcoin", "wallet address",
    })),
)
KEYWORD_CAP = 60

IMPERATIVE_VERBS = frozenset({
    "send", "share", "provide", "enter", "click", "verify", "confirm",
    "update", "submit", "transfer", "pay", "disclose", "reveal",
})
BRANDS = frozenset({
    "rbi", "sbi", "hdfc", "icici", "axis", "kotak", "paytm", "phonepe",
    "gpay", "google pay", "upi", "npci",
})
REQUEST_VERBS = frozenset({
    "verify", "confirm", "update", "provide", "send", "share", "submit",
    "enter", "validate", "authenticate",
})

_DEADLINE_RE = re.compile(r"\b\d+\s*(minutes?|hours?|hrs?|mins?)\b")
_PUNCT_RUN_RE = re.compile(r"([!?])\1{2,}|[!?]{3,}")


# A "do not share"-style warning is the opposite of a disclosure request:
# legitimate OTP notices carry one, scams never do.
NEGATION_TOKENS = frozenset({"not", "never", "dont", "no", "nobody"})
NEGATION_PHRASES = frozenset({"do not", "don't", "never share", "do not share"})


def _word_hit(normalized: str, phrase: str) -> bool:
    if " " in phrase:
        return phrase in normalized
    return re.search(rf"\b{re.escape(phrase)}\b", normalized) is not None


def analyze_message(text: str, *, context: str = "unknown") -> tuple[list[Signal], list[str], list[str]]:
    """Score message text. Returns (signals, matched_phrases, extracted_urls).

    URLs are extracted from the RAW text: leet-folding would corrupt them.
    """
    urls = nz.extract_urls(text)
    normalized, _ = nz.normalize_text(text)
    signals: list[Signal] = []
    matched: list[str] = []
    keyword_total = 0

    def fire(name: str, points: int, observation: str, title: str,
             value: float | None = None) -> None:
        impact = "high" if points >= 20 else "medium" if points >= 10 else "low"
        signals.append(Signal(name=name, value=value, contribution=points,
                              observation=observation, title=title, impact=impact))

    for family, points, phrases in KEYWORD_FAMILIES:
        hits = sorted(p for p in phrases if _word_hit(normalized, p))
        if not hits:
            continue
        allowed = min(points, KEYWORD_CAP - keyword_total)
        if allowed <= 0:
            matched.extend(h for h in hits if h not in matched)
            continue
        keyword_total += allowed
        matched.extend(h for h in hits if h not in matched)
        fire(f"message.{family}", allowed,
             f"Message contains {family} language: {', '.join(hits[:3])}",
             f"{family.replace('_', ' ').title()} language",
             float(len(hits)))

    tokens = set(re.findall(r"[a-z]+", normalized))
    # Deadline pressure: a time limit near urgency language.
    if _DEADLINE_RE.search(normalized) and (tokens & {"urgent", "immediately", "hurry", "expires", "minutes", "hours", "account", "blocked"}):
        m = _DEADLINE_RE.search(normalized)
        fire("message.deadline", 15,
             f"Message imposes a deadline: {m.group(0) if m else 'time limit'}",
             "Deadline pressure")
    # Imperative + credential co-occurrence: being told to hand something over.
    # Skipped when the message warns NOT to share (legitimate OTP notices).
    negated = bool(tokens & NEGATION_TOKENS) or any(p in normalized for p in NEGATION_PHRASES)
    if not negated and tokens & IMPERATIVE_VERBS and tokens & {"otp", "pin", "cvv", "password", "kyc", "account", "card", "aadhaar"}:
        fire("message.imperative_credential", 15,
             "Message instructs the reader to provide credentials or codes",
             "Instruction to disclose credentials")
    # Impersonation: known brand + request verb, sender context unknown.
    # Same negation guard: "never share" warnings are not requests.
    brands_hit = sorted(b for b in BRANDS if _word_hit(normalized, b))
    if not negated and brands_hit and tokens & REQUEST_VERBS:
        fire("message.impersonation", 20,
             f"Message invokes {', '.join(brands_hit[:2])} alongside a verification request",
             "Possible brand impersonation", float(len(brands_hit)))
    # Shouting / hype markers.
    alpha = [c for c in text if c.isalpha()]
    if len(alpha) > 20 and sum(1 for c in alpha if c.isupper()) / len(alpha) > 0.40:
        fire("message.caps_ratio", 8, "Message is largely uppercase", "Shouting text")
    if _PUNCT_RUN_RE.search(text):
        fire("message.punctuation", 5, "Message uses excessive punctuation", "Hype punctuation")

    # Benign guard: fewer than 3 tokens and no hits -> silence.
    if len(tokens) < 3 and not signals:
        return [], [], urls
    return signals, sorted(set(matched)), urls


class MessageAnalyzer:
    name = "message"

    def matches(self, analysis_type: str) -> bool:
        return analysis_type == "message"

    def analyze(self, normalized: object, ctx: dict) -> list[Signal]:
        signals, _, _ = analyze_message(str(normalized), context=str(ctx.get("context", "unknown")))
        return signals
