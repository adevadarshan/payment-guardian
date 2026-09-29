# tests/test_benign_messages.py — Slice 3: legitimate texts must stay SAFE.
# No-false-positive budget: every case below must score < 35.
from app.analyzers.message_analyzer import analyze_message

BENIGN = [
    # EMI debit notice (informational, no request).
    "Your EMI of Rs.4,500 is debited. Available balance Rs.12,000.",
    # OTP delivery notice: states the code, warns against disclosure.
    "Your OTP is 482913. Do not share it with anyone. -SBI",
    # Bill receipt.
    "Payment of Rs.320 received for electricity bill. Thank you!",
    # Personal chat.
    "Are we still meeting for lunch tomorrow?",
    # Bank warning that names the brand but requests nothing.
    "SBI never asks for your OTP or PIN. Stay alert.",
]

BUDGET = 0  # number of benign cases allowed to reach MEDIUM or above


def test_benign_messages_stay_safe():
    offenders = []
    for text in BENIGN:
        signals, _, _ = analyze_message(text)
        total = sum(s.contribution for s in signals)
        if total >= 35:
            offenders.append((text, total, [s.name for s in signals]))
    assert len(offenders) <= BUDGET, offenders
