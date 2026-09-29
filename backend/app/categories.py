# app/categories.py — SINGLE registry for merchant categories (Slice 1).
# The only place that maps a user-facing label to its risk profile.
# Labels mirror the SentinelPay dropdown so the migrated UI keeps its options;
# profile keys/types/weights are our own clean-room definitions.

from typing import TypedDict


class CategoryProfile(TypedDict):
    key: str       # internal profile key
    type: str      # one of PAYMENT | DEBIT | TRANSFER | CASH_OUT
    risk_weight: float  # bounded multiplier used by Slice 2 scoring


CATEGORIES: dict[str, CategoryProfile] = {
    "Groceries": {"key": "GROCERY", "type": "PAYMENT", "risk_weight": 0.8},
    "Utilities": {"key": "UTILITIES", "type": "PAYMENT", "risk_weight": 0.7},
    "Insurance": {"key": "INSURANCE", "type": "PAYMENT", "risk_weight": 0.6},
    "Healthcare": {"key": "HEALTHCARE", "type": "PAYMENT", "risk_weight": 0.8},
    "Education": {"key": "EDUCATION", "type": "PAYMENT", "risk_weight": 0.7},
    "Subscription": {"key": "SUBSCRIPTION", "type": "PAYMENT", "risk_weight": 0.7},
    "Salary / Payroll": {"key": "SALARY", "type": "PAYMENT", "risk_weight": 0.6},
    "Retail / Shopping": {"key": "RETAIL", "type": "DEBIT", "risk_weight": 1.0},
    "Travel": {"key": "TRAVEL", "type": "DEBIT", "risk_weight": 1.1},
    "Entertainment": {"key": "ENTERTAINMENT", "type": "DEBIT", "risk_weight": 1.0},
    "Food & Dining": {"key": "FOOD_DELIVERY", "type": "DEBIT", "risk_weight": 0.9},
    "Electronics": {"key": "ECOMMERCE", "type": "PAYMENT", "risk_weight": 1.1},
    "Fuel": {"key": "FUEL", "type": "DEBIT", "risk_weight": 0.9},
    "Clothing": {"key": "RETAIL", "type": "DEBIT", "risk_weight": 1.0},
    "Peer Transfer": {"key": "PEER_TRANSFER", "type": "TRANSFER", "risk_weight": 1.4},
    "Wallet / Top-up": {"key": "WALLET_TOPUP", "type": "TRANSFER", "risk_weight": 1.3},
    "Remittance": {"key": "REMITTANCE", "type": "TRANSFER", "risk_weight": 1.4},
    "Investment": {"key": "INVESTMENT", "type": "TRANSFER", "risk_weight": 1.2},
    "Loan Repayment": {"key": "LOAN_REPAYMENT", "type": "TRANSFER", "risk_weight": 1.0},
    "ATM / Cash Withdrawal": {"key": "ATM", "type": "CASH_OUT", "risk_weight": 1.6},
    "Cash Advance": {"key": "CASH_ADVANCE", "type": "CASH_OUT", "risk_weight": 1.7},
    "Crypto": {"key": "CRYPTO", "type": "CASH_OUT", "risk_weight": 1.8},
    "Gambling": {"key": "GAMBLING", "type": "CASH_OUT", "risk_weight": 1.9},
    "Other": {"key": "OTHER", "type": "TRANSFER", "risk_weight": 1.2},
}

ALLOWED_CATEGORIES: frozenset[str] = frozenset(CATEGORIES.keys())
