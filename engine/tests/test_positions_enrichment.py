"""Position enrichment across the three position sources.

Regression cover for a 2026-07-27 production failure: `_load_positions` gained a
`$HELD_TICKERS` fallback that yields ticker-only dicts, but the enrichment path did
`p["entry_price"]` unconditionally and the scheduled run died with KeyError after 33
minutes of work. CI uses exactly that source, because book_export.json is gitignored.
"""
import pandas as pd
import pytest
import yaml

from engine.data.base import TickerMeta
from engine.pipeline import enrich_positions


@pytest.fixture
def cfg():
    return yaml.safe_load(open("engine/config.yaml"))


@pytest.fixture
def hist():
    idx = pd.date_range("2026-04-01", periods=80, freq="B")
    close = pd.Series(range(50, 130), index=idx, dtype=float)
    return {
        "AAA": pd.DataFrame(
            {"open": close, "high": close * 1.02, "low": close * 0.98,
             "close": close, "volume": [1e6] * 80},
            index=idx,
        )
    }


@pytest.fixture
def meta_by():
    return {"AAA": TickerMeta("AAA", "Alpha Corp", "CS", "XNAS", "Tech")}


def test_held_tickers_entry_has_no_cost_basis(hist, meta_by, cfg):
    """The exact shape $HELD_TICKERS produces — must not raise, must not invent P&L."""
    out = enrich_positions([{"ticker": "AAA"}], hist, meta_by, cfg)
    assert len(out) == 1
    assert out[0]["name"] == "Alpha Corp"      # still enriched
    assert "exit" not in out[0]                # but no exit grade without an entry


def test_lot_with_cost_basis_gets_exit_grade(hist, meta_by, cfg):
    out = enrich_positions(
        [{"ticker": "AAA", "entry_price": 60.0, "shares": 10}], hist, meta_by, cfg
    )
    assert "exit" in out[0]
    assert out[0]["exit"]["price"] > 0


def test_high_watermark_defaults_to_entry(hist, meta_by, cfg):
    """A book export has no high_watermark; entry is the correct floor."""
    a = enrich_positions([{"ticker": "AAA", "entry_price": 60.0}], hist, meta_by, cfg)
    b = enrich_positions(
        [{"ticker": "AAA", "entry_price": 60.0, "high_watermark": 60.0}], hist, meta_by, cfg
    )
    assert a[0]["exit"] == b[0]["exit"]


def test_unknown_and_unpriced_tickers_survive(hist, meta_by, cfg):
    """A held name with no history must pass through, not vanish or raise."""
    out = enrich_positions(
        [{"ticker": "ZZZ"}, {"ticker": "AAA", "entry_price": 60.0}], hist, meta_by, cfg
    )
    assert [p["ticker"] for p in out] == ["ZZZ", "AAA"]
    assert "exit" not in out[0]


def test_empty_and_none(hist, meta_by, cfg):
    assert enrich_positions([], hist, meta_by, cfg) == []
    assert enrich_positions(None, hist, meta_by, cfg) == []


def test_zero_entry_price_is_not_treated_as_a_basis(hist, meta_by, cfg):
    """0 would make R-multiples divide by zero; treat it as absent."""
    out = enrich_positions([{"ticker": "AAA", "entry_price": 0}], hist, meta_by, cfg)
    assert "exit" not in out[0]
