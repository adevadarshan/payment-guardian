# User-facing explanation for Slice 4 — deterministic templates grounded ONLY in observed signals; never certainty, never invented facts

EXPLANATIONS = {
    "urgency": 'The message pressures you to act quickly (found: {evidence}). Time pressure is a common persuasion tactic, but legitimate deadlines also exist.',
    "reward_or_prize": 'The message claims you have won or will receive something (found: {evidence}). Unsolicited prize claims are a common lure.',
    "refund_claim": 'The message mentions a refund or credit (found: {evidence}). Refund messages can be faked; check the status in the official app instead.',
    "payment_request": 'The message asks you to send money or make a payment (found: {evidence}). Do not pay in response to an unsolicited message without independent verification.',
    "otp_or_pin_request": 'The message involves a one-time password, PIN, or code (found: {evidence}). Never share OTPs, PINs, or codes with anyone.',
    "account_or_credential_request": 'The message asks for account or identity details (found: {evidence}). Do not share these through unsolicited messages or links.',
    "impersonation": 'The message names an authority or brand (found: {evidence}). Names are easy to impersonate; verify the sender through an official channel.',
    "scan_or_click_action": 'The message asks you to scan a QR code or click a link (found: {evidence}). These can lead to phishing pages or payment requests.',
}

SUMMARIES = {
    "LOW": "Low risk: no significant warning signals were found in this message. Stay alert and verify independently.",
    "MEDIUM": "Medium risk: this message contains some suspicious signals. Verify through official channels before acting.",
    "HIGH": "High risk: this message contains several warning signals. Do not proceed without independent verification.",
    "CRITICAL": "Critical risk: this message shows a strong pattern of warning signals. Do not proceed.",
}

ACTIONS = {
    "urgency": "Take your time. Contact the organization through its official app or website instead of acting from this message.",
    "reward_or_prize": "Do not pay any fee or share details to claim a prize. Verify the offer through the official source.",
    "refund_claim": "Check the refund status in the official app or website. Do not follow links or QR codes in this message.",
    "payment_request": "Do not send money or pay until you have independently verified the recipient.",
    "otp_or_pin_request": "Do not share OTPs, PINs, or codes with anyone, even if the message asks.",
    "account_or_credential_request": "Do not enter account details, passwords, or identity documents through links or messages you did not request.",
    "impersonation": "Verify the sender independently through the official helpline, app, or website.",
    "scan_or_click_action": "Do not scan QR codes or click links in unsolicited messages.",
}

DEFAULT_ACTION = "No action needed. Stay alert and verify independently."


def build_explanation(signals: list, risk_level: str, risk_score: float) -> dict:
    """Deterministic user-facing explanation. Grounded ONLY in matched signals + level.
    Returns {"summary": str, "explanation": list[str], "actions": list[str]}."""
    explanation = []
    actions = []
    for signal in signals:
        signal_type = signal.get("type")
        if not signal.get("matched") or signal_type not in EXPLANATIONS:
            continue
        evidence = ", ".join('"%s"' % term for term in signal.get("evidence", []))
        explanation.append(EXPLANATIONS[signal_type].format(evidence=evidence))
        action = ACTIONS[signal_type]
        if action not in actions:
            actions.append(action)
    if not actions:
        actions = [DEFAULT_ACTION]
    return {
        "summary": SUMMARIES.get(risk_level, SUMMARIES["MEDIUM"]),
        "explanation": explanation,
        "actions": actions,
    }
