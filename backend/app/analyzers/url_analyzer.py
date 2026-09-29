# app/analyzers/url_analyzer.py — deterministic URL signals (Slice 3).
# Stdlib urllib.parse only. No DNS, no WHOIS, no fetching, no reputation APIs.
# A risky-host match is an indicator, never proof of maliciousness.

import ipaddress
import json
import re
from pathlib import Path

from app.pipeline import normalize as nz
from app.pipeline.signals import Signal

SHORTENERS = frozenset({
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd",
    "cutt.ly", "rb.gy", "s.id", "tiny.cc",
})

PATH_KEYWORDS = frozenset({
    "login", "verify", "otp", "payment", "kyc", "refund",
    "wallet", "apk", "update", "secure",
})
EXFIL_PARAMS = frozenset({
    "email", "phone", "otp", "pin", "cc", "pan", "upi",
    "account", "password",
})
REDIRECT_PARAMS = frozenset({
    "url", "next", "redirect", "return", "continue", "dest",
})


def _risky_hosts() -> frozenset[str]:
    # Curated demo/test heuristic data (see app/data/risky_hosts.json).
    # A match is an indicator, never proof of maliciousness.
    path = Path(__file__).parent.parent / "data" / "risky_hosts.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return frozenset(h.lower() for h in data.get("hosts", []))
    except (OSError, ValueError):
        return frozenset()


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _registrable(host: str) -> str:
    labels = host.split(".")
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


def analyze_url_parts(parts: dict) -> tuple[list[Signal], list[str]]:
    """Score normalized URL parts. Returns (signals, matched_fragments)."""
    signals: list[Signal] = []
    matched: list[str] = []
    host = parts["host"]

    def fire(code: str, points: int, observation: str, value: float | None = None,
             title: str = "") -> None:
        impact = "high" if points >= 20 else "medium" if points >= 10 else "low"
        signals.append(Signal(name=code, value=value, contribution=points,
                              observation=observation,
                              title=title or code.split(".", 1)[-1].replace("_", " ").title(),
                              impact=impact))
        matched.append(observation)

    if _is_ip(host):
        fire("url.ip_host", 25, f"Host is an IP literal: {host}")
    if host.startswith("xn--") or ".xn--" in host:
        fire("url.punycode", 20, f"Host uses punycode: {host}")
    authority = parts["raw"].split("://", 1)[-1].split("/", 1)[0]
    if "@" in authority:
        fire("url.at_sign", 15, "URL contains @ in the authority section")
    if parts["has_credentials"]:
        fire("url.embedded_credentials", 20, "URL embeds credentials before @")
    if parts["scheme"] != "https":
        fire("url.not_https", 10, f"URL uses non-HTTPS scheme: {parts['scheme'] or '(none)'}")
    if parts["port"] is not None:
        fire("url.explicit_port", 8, f"URL uses explicit port {parts['port']}")

    labels = host.split(".")
    if len(labels) >= 4:  # e.g. a.b.c.example.com
        fire("url.deep_subdomain", 10, f"Host has {len(labels) - 2} subdomain levels")
    registrable = _registrable(host)
    for brand in ("paypal", "google", "apple", "amazon", "microsoft", "facebook",
                  "instagram", "whatsapp", "sbi", "hdfc", "icici", "axis",
                  "phonepe", "paytm", "upi", "rbi"):
        if brand in host and brand not in registrable:
            fire("url.brand_in_subdomain", 30,
                 f"Brand name '{brand}' appears outside the registrable domain ({registrable})")
            break
    if host.count("-") >= 3:
        fire("url.hyphens", 8, "Host contains 3+ hyphens")
    if host in SHORTENERS:
        fire("url.shortener", 15, f"URL uses a link shortener: {host}")

    path = parts["path"].lower()
    path_hits = sorted(k for k in PATH_KEYWORDS if k in path)
    if path_hits:
        fire("url.suspicious_path", min(20, 10 * len(path_hits)),
             f"Path contains keywords: {', '.join(path_hits[:3])}")

    query = parts["query"].lower()
    params = [p.split("=", 1)[0] for p in query.split("&") if p]
    exfil = sorted(p for p in params if p in EXFIL_PARAMS)
    if exfil:
        fire("url.exfil_params", 15,
             f"Query carries data-collection parameters: {', '.join(exfil[:3])}")
    redirect = sorted(p for p in params if p in REDIRECT_PARAMS)
    if redirect:
        fire("url.redirect_params", 10,
             f"Query carries redirect parameters: {', '.join(redirect[:3])}")
    if len(parts["query"]) > 200 or re.search(r"(?:%[0-9a-fA-F]{2}){4,}", parts["query"]):
        fire("url.long_query", 8, "Query string is unusually long or encoded")

    if host in _risky_hosts():
        fire("url.risky_host", 30,
             f"Host is on the curated risky-host list (indicator, not proof): {host}")

    return signals, matched


def analyze_url(raw: str) -> tuple[list[Signal], list[str]]:
    """Score a raw URL string. Raises ValueError when unusable."""
    return analyze_url_parts(nz.normalize_url(raw))


class UrlAnalyzer:
    name = "url"

    def matches(self, analysis_type: str) -> bool:
        return analysis_type == "url"

    def analyze(self, normalized: object, ctx: dict) -> list[Signal]:
        signals, _ = analyze_url(str(normalized))
        return signals
