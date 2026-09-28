# Signal extraction for Slice 2 — deterministic, English-only
# signal detected != scam confirmed
# signal not detected != safe
import re

URGENCY = ["immediately", "urgent", "urgently", "right now", "within 24 hours", "act now", "do not delay", "limited time", "expires today", "last chance", "time sensitive", "as soon as possible", "asap"]
REWARD = ["congratulations", "you have won", "you've won", "you are selected", "you have been selected", "lucky winner", "prize", "lottery", "jackpot", "cashback offer", "free gift", "bonus credited"]
REFUND = ["refund", "cashback", "amount has been credited", "money has been credited"]
PAYMENT = ["send money", "transfer money", "transfer funds", "pay now", "make a payment", "complete the payment", "pay ₹", "pay rs", "send ₹", "google pay", "gpay", "phonepe", "paytm", "upi id", "upi transfer", "neft", "imps"]
OTP = ["otp", "one time password", "one-time password", "pin", "passcode", "security code", "verification code", "enter the code", "share the code", "do not share", "never share your otp"]
ACCOUNT = ["account number", "card number", "cvv", "expiry date", "atm pin", "net banking", "password", "aadhaar", "aadhar", "pan number", "date of birth", "your bank details", "verify your account", "confirm your identity", "kyc", "kyc update", "kyc pending"]
IMPERSONATION = ["rbi", "reserve bank", "trai", "income tax department", "it department", "central government", "state government", "cyber crime", "police", "narcotics", "enforcement directorate", "ed notice", "court notice", "your bank", "sbi", "hdfc", "icici", "axis bank", "customer care", "helpdesk", "official helpline"]
SCAN = ["scan", "scan the qr", "qr code", "click here", "click the link", "click below", "tap here", "follow the link", "open the link", "visit the link", "download the app", "install the app"]


def _matches(text: str, keyword: str) -> bool:
    if ' ' in keyword:
        return keyword in text
    return bool(re.search(r'\b' + re.escape(keyword) + r'\b', text))


def _extract_signal(normalized: str, signal_type: str, keywords: list) -> dict:
    evidence = [kw for kw in keywords if _matches(normalized, kw)]
    return {"type": signal_type, "matched": bool(evidence), "evidence": evidence}


def analyze(message: str) -> list:
    normalized = " ".join(message.lower().split())
    return [
        _extract_signal(normalized, "urgency", URGENCY),
        _extract_signal(normalized, "reward_or_prize", REWARD),
        _extract_signal(normalized, "refund_claim", REFUND),
        _extract_signal(normalized, "payment_request", PAYMENT),
        _extract_signal(normalized, "otp_or_pin_request", OTP),
        _extract_signal(normalized, "account_or_credential_request", ACCOUNT),
        _extract_signal(normalized, "impersonation", IMPERSONATION),
        _extract_signal(normalized, "scan_or_click_action", SCAN),
    ]
