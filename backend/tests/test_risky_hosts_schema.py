# tests/test_risky_hosts_schema.py — Slice 4 increment 6: curated list hygiene.
import json
import re
from pathlib import Path

HOST_RE = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))+$")


def _load():
    path = Path(__file__).resolve().parents[1] / "app" / "data" / "risky_hosts.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_risky_hosts_schema():
    data = _load()
    assert "_comment" in data or any(k.startswith("_") for k in data), \
        "curated file must carry a provenance/disclaimer comment"
    hosts = data.get("hosts", [])
    assert 0 < len(hosts) <= 50
    lowered = [h.lower() for h in hosts]
    assert lowered == sorted(lowered), "hosts must be sorted"
    assert len(set(lowered)) == len(lowered), "hosts must be de-duplicated"
    for host in lowered:
        assert HOST_RE.match(host), host
    for entry in data.get("entries", []):
        assert entry.get("host") in lowered and entry.get("reason"), entry


def test_risky_hosts_documented_as_indicator():
    path = Path(__file__).resolve().parents[1] / "app" / "data" / "risky_hosts.json"
    text = path.read_text(encoding="utf-8").lower()
    assert "indicator" in text and "never proof" in text.replace("  ", " ") or "not proof" in text
