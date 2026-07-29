"""Per-endpoint Finnhub cache lifetimes.

Fundamentals were ~95% of a cold scan (fundamentals+features 1421s + earnings 503s of
a 2029s run, measured 2026-07-28) purely because one global 20h TTL refetched
everything daily — including a company's sector, which never changes. These tests pin
each endpoint to a lifetime matching how fast its data actually moves.
"""
import yaml

from engine.data.finnhub import FinnhubProvider


class _Recorder:
    """Captures the ttl each call was made with, without touching the network."""

    def __init__(self):
        self.calls = []

    def __call__(self, url, params, limiter, ttl_hours, cache_key=None, timeout=30):
        self.calls.append({"url": url, "ttl": ttl_hours, "key": cache_key})
        return {}

    def ttl_for(self, fragment):
        return next(c["ttl"] for c in self.calls if fragment in c["url"])


def _provider(monkeypatch, rec):
    monkeypatch.setenv("FINNHUB_API_KEY", "test-key")
    monkeypatch.setattr("engine.data.finnhub.cached_get", rec)
    return FinnhubProvider()


def test_each_endpoint_gets_its_own_ttl(monkeypatch):
    rec = _Recorder()
    p = _provider(monkeypatch, rec)
    p.get_earnings(["AAA"])
    p.get_recommendation("AAA")
    p.get_financials("AAA")
    p.get_sector("AAA")

    cfg = yaml.safe_load(open("engine/config.yaml"))["data"]["finnhub"]["ttl_hours"]
    assert rec.ttl_for("/calendar/earnings") == cfg["earnings"]
    assert rec.ttl_for("/stock/recommendation") == cfg["recommendation"]
    assert rec.ttl_for("/stock/metric") == cfg["financials"]
    assert rec.ttl_for("/stock/profile2") == cfg["profile"]


def test_slow_moving_data_outlives_a_run_day(monkeypatch):
    """The whole point: anything quarterly-or-slower must survive to the next run,
    or the cache saves nothing."""
    rec = _Recorder()
    p = _provider(monkeypatch, rec)
    p.get_financials("AAA")
    p.get_sector("AAA")
    assert rec.ttl_for("/stock/metric") > 24
    assert rec.ttl_for("/stock/profile2") > 24 * 7


def test_earnings_still_refreshes_daily(monkeypatch):
    """Earnings dates get revised — this one must NOT be cached long."""
    rec = _Recorder()
    p = _provider(monkeypatch, rec)
    p.get_earnings(["AAA"])
    assert rec.ttl_for("/calendar/earnings") <= 24


def test_unknown_kind_falls_back_to_global_ttl(monkeypatch):
    rec = _Recorder()
    p = _provider(monkeypatch, rec)
    p._get("/whatever", {}, key="k")
    assert rec.calls[-1]["ttl"] == p._ttl


def test_rate_limit_stays_under_the_free_tier(monkeypatch):
    """Sitting exactly on 60/min trips 429s and the 5/10/20/40s backoff costs more
    than the spacing saves."""
    cfg = yaml.safe_load(open("engine/config.yaml"))["data"]["finnhub"]
    assert cfg["rate_limit_per_min"] < 60
