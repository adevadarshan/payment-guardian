# tests/test_benign_urls.py — Slice 3: official domains stay SAFE.
from app.analyzers.url_analyzer import analyze_url

BENIGN = [
    "https://www.hdfcbank.com/",
    "https://www.onlinesbi.sbi/",
    "https://www.amazon.in/gp/cart/view.html",
    "https://uidai.gov.in/",
]


def test_benign_urls_stay_safe():
    offenders = []
    for raw in BENIGN:
        signals, _ = analyze_url(raw)
        total = sum(s.contribution for s in signals)
        if total >= 35:
            offenders.append((raw, total, [s.name for s in signals]))
    assert offenders == []
