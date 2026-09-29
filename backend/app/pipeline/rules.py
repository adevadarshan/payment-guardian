# app/pipeline/rules.py — pure deterministic payment-scoring primitives (Slice 2).
# Clean-room reimplementation of observable SentinelPay payment-analysis behaviour.
# This is NOT the original XGBoost/Isolation Forest model (artifacts quarantined,
# never used). Rules below: no randomness, no clock reads, no DB access.

import math
import re

# Additive amount tiers, highest-first: (minimum amount, points).
AMOUNT_TIERS: tuple[tuple[float, int], ...] = (
    (100000, 45),
    (50000, 35),
    (20000, 30),
    (10000, 25),
    (5000, 15),
    (2000, 10),
    (500, 4),
)

# Flat category contributions by user-facing label (mirrors the 24-label registry).
CATEGORY_POINTS: dict[str, int] = {
    "Crypto": 25,
    "Gambling": 25,
    "Cash Advance": 20,
    "ATM / Cash Withdrawal": 20,
    "Travel": 20,
    "Electronics": 20,
    "Peer Transfer": 12,
    "Remittance": 12,
    "Wallet / Top-up": 12,
    "Entertainment": 10,
    "Clothing": 10,
    "Retail / Shopping": 10,
    "Fuel": 10,
    "Food & Dining": 6,
    "Investment": 6,
    "Loan Repayment": 6,
    "Groceries": 0,
    "Utilities": 0,
    "Insurance": 0,
    "Healthcare": 0,
    "Education": 0,
    "Subscription": 0,
    "Salary / Payroll": 0,
    "Other": 8,
}

URGENT_WORDS: frozenset[str] = frozenset({"urgent", "blocked", "suspend", "otp", "prize"})
INFO_WORDS: frozenset[str] = frozenset({"kyc", "verify", "claim", "refund"})

DRAIN_CEILING_RATIO = 0.90
DRAIN_ELEVATED_RATIO = 0.60
DRAIN_CEILING_SCORE = 85
DRAIN_ELEVATED_POINTS = 15
UPI_LIMIT = 200000.0
MAGNITUDE_SCALE = 75.0


def amount_tier(amount: float) -> tuple[int, str | None]:
    """Additive points for the amount tier. Returns (points, tier label or None)."""
    for minimum, points in AMOUNT_TIERS:
        if amount >= minimum:
            return points, f"Rs.{int(minimum):,}"
    return 0, None


def category_points(label: str) -> tuple[int, bool]:
    """Additive points for a registry label. Returns (points, known)."""
    if label not in CATEGORY_POINTS:
        return 0, False
    return CATEGORY_POINTS[label], True


def hour_points(hour: int | None) -> tuple[int, str | None]:
    """Additive points for hour-of-day. None-safe: unknown hour contributes nothing."""
    if hour is None:
        return 0, None
    if 0 <= hour <= 4:
        return 20, "night"
    if 22 <= hour <= 23:
        return 10, "late"
    return 0, None


def drain_ratio(amount: float, balance: float) -> float:
    return amount / (balance + 1.0)


def magnitude_floor(amount: float) -> int:
    """Sigmoid curve rising toward the UPI limit, scaled to MAGNITUDE_SCALE."""
    return round(MAGNITUDE_SCALE / (1.0 + math.exp(-10.0 * (amount / UPI_LIMIT - 0.5))))


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def note_hits(note: str | None) -> tuple[str | None, list[str]]:
    """Keyword family match. Returns ("urgent"|"info"|None, matched phrases).

    Urgent wins when both families match (mirrors upstream if/elif).
    """
    if not note:
        return None, []
    tokens = set(_words(note))
    urgent = sorted(tokens & URGENT_WORDS)
    if urgent:
        return "urgent", urgent
    info = sorted(tokens & INFO_WORDS)
    if info:
        return "info", info
    return None, []


def payee_unverified(payee_name: str | None) -> bool:
    if payee_name is None:
        return True
    stripped = payee_name.strip()
    return not stripped or stripped.lower() == "unknown"
