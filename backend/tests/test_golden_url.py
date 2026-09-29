# tests/test_golden_url.py — Slice 3 increment 4: URL corpus.
# Hand-written phishing archetypes + danger-structural cases.
from app.analyzers.url_analyzer import analyze_url


def _score(raw):
    signals, matched = analyze_url(raw)
    return sum(s.contribution for s in signals), [s.name for s in signals]


CASES = [
    ("brand in subdomain + exfil",
     "http://paypal.com.secure-login.xyz/verify?email=x",
     "HIGH", ["url.brand_in_subdomain", "url.exfil_params"]),
    ("ip host",
     "http://185.22.1.4/login?user=a",
     "MEDIUM", ["url.ip_host"]),
    ("punycode + verify + exfil",
     "https://xn--sbi-xyz.com/verify?otp=1",
     "MEDIUM", ["url.punycode"]),
    ("shortener restraint",
     "https://bit.ly/3xYzAbC",
     "SAFE", ["url.shortener"]),
    ("credentials in url",
     "https://user:pass@secure.example.com/account",
     "MEDIUM", ["url.embedded_credentials"]),
    ("port + redirect",
     "http://example.com:8080/login?next=/home",
     "MEDIUM", ["url.explicit_port", "url.redirect_params"]),
    ("hyphenated host",
     "https://secure-login-verify-account-xyz.com/",
     "SAFE", ["url.hyphens"]),
    ("risky host list",
     "https://upi-kyc-update.top/verify",
     "MEDIUM", ["url.risky_host"]),
    ("deep subdomain",
     "https://login.a.b.example.com/verify",
     "SAFE", ["url.deep_subdomain"]),
]


def test_golden_url():
    for name, raw, level, codes in CASES:
        total, names = _score(raw)
        if level == "HIGH":
            assert total >= 75, (name, total, names)
        elif level == "MEDIUM":
            assert 35 <= total < 75, (name, total, names)
        else:
            assert total < 35, (name, total, names)
        for code in codes:
            assert code in names, (name, names)
