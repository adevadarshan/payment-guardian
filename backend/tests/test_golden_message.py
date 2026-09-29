# tests/test_golden_message.py — Slice 3 increment 3: scam corpus.
# Each case: expected band + expected signal-code subset. Inline literals with
# provenance: hand-written scam archetypes (Indian UPI phishing patterns).
from app.analyzers.message_analyzer import analyze_message


def _score(text):
    signals, matched, _ = analyze_message(text)
    return sum(s.contribution for s in signals), [s.name for s in signals], matched


CASES = [
    ("urgency+credential classic",
     "Your account will be blocked in 10 minutes. Verify OTP now.",
     "HIGH", ["message.pressure", "message.credential", "message.deadline",
              "message.imperative_credential"]),
    ("kyc suspend",
     "Dear customer your SBI KYC is suspended. Update immediately on the link or account frozen.",
     "HIGH", ["message.credential", "message.impersonation"]),
    ("prize incentive",
     "Congratulations! You have WON a lottery prize of Rs.50000. Claim now, pay Rs.199 fee!!!",
     "MEDIUM", ["message.incentive", "message.pressure"]),
    ("threat authority",
     "Cyber cell notice: legal action and arrest if you do not pay within 2 hours. Call now.",
     "MEDIUM", ["message.threat", "message.pressure"]),
    ("gift card",
     "Buy a Google Play gift card of Rs.5000 and share the code to unlock your refund.",
     "HIGH", ["message.gift_crypto"]),
    ("leet evasion",
     "V3rify your 0TP urg3ntly, account bl0cked",
     "HIGH", ["message.credential", "message.urgency"]),
]


def test_golden_message():
    for name, text, level, codes in CASES:
        total, names, matched = _score(text)
        if level == "HIGH":
            assert total >= 75, (name, total, names)
        elif level == "MEDIUM":
            assert 35 <= total < 75, (name, total, names)
        else:
            assert total < 35, (name, total, names)
        for code in codes:
            assert code in names, (name, names)
        assert matched, name


def test_benign_guard_short_text():
    signals, matched, _ = analyze_message("ok thanks")
    assert signals == [] and matched == []


def test_urls_extracted_from_raw_text():
    signals, _, urls = analyze_message("Verify at http://user@example.com/login now")
    assert urls == ["http://user@example.com/login"]
