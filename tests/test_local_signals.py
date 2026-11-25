"""Local Signals on the staff Overview: place terms, relevance, recency and caching (network mocked)."""
import os
import sys
from datetime import datetime, timedelta

os.environ.setdefault("JWT_SECRET", "test-secret-key-32-characters-minimum-ok")
os.environ.setdefault("ENV", "test")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from modules import news_intel as N  # noqa: E402

NOW = datetime(2026, 11, 25, 9, 0)
CTX = {"constituency": "Belgaum Dakshin", "leader": "Sanket Jadhav", "state": "Karnataka",
       "cities": ["Belgaum", "Belagavi"], "localities": ["Tilakwadi", "Shahapur"]}


def _art(title, days_ago, source="Pudhari"):
    return {"title": title, "link": f"https://news.example/{abs(hash(title))}", "source": source,
            "published": NOW - timedelta(days=days_ago)}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    N._LOCAL_SIGNAL_CACHE.clear()
    monkeypatch.setattr(N, "_local_signal_context", lambda tid: dict(CTX))
    yield
    N._LOCAL_SIGNAL_CACHE.clear()


def test_city_variants_strip_seat_suffix_and_add_both_spellings():
    assert N._city_variants("Belgaum Dakshin") == ["Belgaum", "Belagavi"]
    assert N._city_variants("Pune Cantonment", "Pune") == ["Pune", "Poona"]
    assert N._city_variants("Chandni Chowk") == ["Chandni Chowk"]


def test_queries_use_city_localities_and_state_language():
    qs = N._local_signal_queries(CTX)
    joined = " | ".join(q for q, _ in qs)
    assert '"Belgaum Dakshin"' in joined and '"Belagavi"' in joined and '"Tilakwadi"' in joined
    assert ("Kannada" in {lang for _, lang in qs}) and len(qs) <= 6


def test_keeps_only_local_recent_items_newest_first(monkeypatch):
    feed = [_art("Tilakwadi residents block road over potholes", 1), _art("Sensex climbs 500 points", 0),
            _art("Belagavi police step up night patrols in Shahapur", 3),
            _art("Belagavi police step up night patrols in Shahapur", 3, "Lokmat"),   # duplicate
            _art("Old Belagavi flyover story", 40), _art("Belgaum civic body clears drains", 6)]
    monkeypatch.setattr(N, "_fetch_rss_timed", lambda q, lang, limit, timeout: list(feed))
    out = N.fetch_local_signals(2, now=NOW)
    titles = [a["title"] for a in out]
    assert titles == ["Tilakwadi residents block road over potholes",
                      "Belagavi police step up night patrols in Shahapur", "Belgaum civic body clears drains"]
    assert all(isinstance(a["published"], str) for a in out)


def test_widens_to_30_days_when_the_fortnight_is_quiet(monkeypatch):
    feed = [_art("Belagavi water board repairs main", 20), _art("Tilakwadi school roof repaired", 25),
            _art("Belgaum market fire", 28), _art("Belgaum fair", 45)]
    monkeypatch.setattr(N, "_fetch_rss_timed", lambda q, lang, limit, timeout: list(feed))
    assert len(N.fetch_local_signals(2, now=NOW)) == 3


def test_results_are_cached_per_tenant(monkeypatch):
    calls = []

    def fake(q, lang, limit, timeout):
        calls.append(q)
        return [_art("Belagavi news", 1)]
    monkeypatch.setattr(N, "_fetch_rss_timed", fake)
    first = N.fetch_local_signals(2, now=NOW)
    n = len(calls)
    assert N.fetch_local_signals(2, now=NOW) == first and len(calls) == n
    N.fetch_local_signals(3, now=NOW)
    assert len(calls) > n


def test_network_failure_returns_empty_without_raising(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("offline")
    monkeypatch.setattr(N, "_fetch_rss_timed", boom)
    assert N.fetch_local_signals(2, now=NOW) == []


def test_no_tenant_context_means_no_search(monkeypatch):
    monkeypatch.setattr(N, "_local_signal_context", lambda tid: {"constituency": "", "cities": [], "localities": [],
                                                                  "leader": "", "state": ""})
    monkeypatch.setattr(N, "_fetch_rss_timed", lambda *a, **k: pytest.fail("should not fetch"))
    assert N.fetch_local_signals(2, now=NOW) == []


def test_rss_parsing_strips_source_suffix_and_skips_undated(monkeypatch):
    rss = b"""<?xml version="1.0"?><rss version="2.0"><channel>
      <item><title>Tilakwadi road blocked - Pudhari</title><link>https://n/1</link>
        <pubDate>Mon, 24 Nov 2026 10:00:00 GMT</pubDate><source url="https://p">Pudhari</source></item>
      <item><title>No date here - X</title><link>https://n/2</link></item>
    </channel></rss>"""

    class R:
        status_code = 200
        content = rss
    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: R())
    items = N._fetch_rss_timed("q", "English", 10, 1.0)
    assert [(i["title"], i["source"]) for i in items] == [("Tilakwadi road blocked", "Pudhari")]
