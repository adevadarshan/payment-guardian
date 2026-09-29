# tests/test_advisory.py — Slice 4 increment 5: isolation, redaction, failure modes.

from app.services import advisory as advisory_service
from tests.conftest import client, payment_payload

REASONS = [
    {"code": "payment.amount_tier", "signal": "s", "title": "Large transaction amount",
     "observation": "Amount Rs.12000 crosses the Rs.10000 tier", "impact": "high"},
]


def test_advisory_disabled_by_default():
    body = client.post("/api/analyze", json=payment_payload()).json()
    assert body["advisory"] == {"status": "disabled", "provider": None, "text": None}


def test_advisory_never_changes_score_all_types(monkeypatch):
    import app.config as config_module

    class LoudStub:
        name = "loud-stub"

        def generate(self, redacted, *, timeout_s):
            return "EXTREME: block everything, panic now, score 100/100!!!"

    monkeypatch.setattr(advisory_service, "StubProvider", LoudStub)
    monkeypatch.setattr(config_module.settings, "ADVISORY_ENABLED", True)
    bodies = [
        {"analysis_type": "payment", "payment": payment_payload()["payment"]},
        {"analysis_type": "message", "message": {"text": "Hello friend, see you soon"}},
        {"analysis_type": "url", "url": {"url": "https://www.hdfcbank.com/"}},
        {"analysis_type": "qr", "qr": {"payload": "upi://pay?pa=quiet@upi&pn=Quiet"}},
    ]
    for body in bodies:
        data = client.post("/api/analyze", json=body).json()
        assert data["advisory"]["status"] == "ok"
        assert data["advisory"]["text"]
        for key in ("risk_score", "risk_level", "reasons", "signals"):
            assert key in data
        # The persisted verdict is untouched by advisory: re-read from history.
        stored = client.get(f"/api/scans/{data['scan_id']}").json()
        assert stored["risk_score"] == data["risk_score"]
        assert stored["risk_level"] == data["risk_level"]
        assert stored["reasons"] == data["reasons"]
        assert stored["signals"] == data["signals"]
        assert stored["advisory"]["status"] == "disabled"


def test_advisory_timeout_and_error_paths(monkeypatch):
    import app.config as config_module

    class Slow:
        name = "slow"

        def generate(self, redacted, *, timeout_s):
            import time
            time.sleep(timeout_s + 2)
            return "too late"

    class Broken:
        name = "broken"

        def generate(self, redacted, *, timeout_s):
            raise RuntimeError("boom")

    monkeypatch.setattr(config_module.settings, "ADVISORY_ENABLED", True)
    monkeypatch.setattr(advisory_service, "StubProvider", Slow)
    monkeypatch.setattr(config_module.settings, "ADVISORY_TIMEOUT_S", 1)
    body = payment_payload()
    data = client.post("/api/analyze", json=body).json()
    assert data["advisory"]["status"] == "timeout"
    assert data["risk_score"] is not None  # verdict intact

    monkeypatch.setattr(advisory_service, "StubProvider", Broken)
    data = client.post("/api/analyze", json=body).json()
    assert data["advisory"]["status"] == "error"


def test_advisory_input_redaction():
    # Only static titles/codes cross the provider boundary — never raw text.
    redacted = advisory_service.redact_input(
        analysis_type="message", risk_level="HIGH",
        reasons=[{"code": "message.credential", "signal": "s",
                  "title": "Credential request",
                  "observation": "Note contains pressure words: otp, pa=secret@upi"}],
        seen_status="new", evidence_kinds=["phrases"])
    blob = str(redacted).lower()
    assert "secret@upi" not in blob
    assert "pressure words" not in blob
    assert "credential request" in blob  # static titles are allowed


def test_advisory_text_length_cap():
    class Long:
        name = "long"

        def generate(self, redacted, *, timeout_s):
            return "x" * 5000

    import app.services.advisory as svc
    real = svc.StubProvider
    svc.StubProvider = Long
    try:
        out = svc.advise(
            enabled=True, provider_name="stub", endpoint=None, api_key=None,
            timeout_s=5, max_chars=100, analysis_type="url", risk_level="SAFE",
            reasons=[], seen_status="not_applicable", evidence_kinds=[])
    finally:
        svc.StubProvider = real
    assert out["status"] == "ok" and len(out["text"] or "") <= 100
