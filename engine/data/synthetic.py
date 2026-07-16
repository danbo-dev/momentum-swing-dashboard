"""Deterministic synthetic data so the engine runs/verifies without API keys.

Generates a small universe of tickers spanning uptrend / downtrend / choppy
regimes (so scoring produces a realistic spread), plus SPY as the benchmark,
and synthetic earnings / recommendation / financials.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import (
    Earnings,
    Financials,
    FundamentalProvider,
    PriceProvider,
    Recommendation,
    TickerMeta,
)

# (ticker, name, type, annual_drift, annual_vol, start_price)
_SPEC = [
    ("SPY", "S&P 500 ETF", "ETF", 0.10, 0.15, 450.0),
    ("NVDA", "NVIDIA Corp", "CS", 0.55, 0.40, 95.0),
    ("META", "Meta Platforms", "CS", 0.35, 0.32, 480.0),
    ("AVGO", "Broadcom Inc", "CS", 0.40, 0.34, 140.0),
    ("AAPL", "Apple Inc", "CS", 0.18, 0.24, 190.0),
    ("MSFT", "Microsoft Corp", "CS", 0.22, 0.23, 420.0),
    ("AMZN", "Amazon.com", "CS", 0.28, 0.30, 185.0),
    ("GOOGL", "Alphabet Inc", "CS", 0.20, 0.26, 175.0),
    ("LLY", "Eli Lilly", "CS", 0.42, 0.30, 780.0),
    ("COST", "Costco", "CS", 0.24, 0.20, 850.0),
    ("JPM", "JPMorgan Chase", "CS", 0.16, 0.22, 205.0),
    ("XOM", "Exxon Mobil", "CS", 0.06, 0.24, 115.0),
    ("WMT", "Walmart", "CS", 0.26, 0.18, 68.0),
    ("PANW", "Palo Alto Networks", "CS", 0.30, 0.38, 320.0),
    ("UBER", "Uber Technologies", "CS", 0.34, 0.36, 72.0),
    ("SHOP", "Shopify", "CS", 0.32, 0.45, 78.0),
    ("AMD", "Advanced Micro Devices", "CS", 0.12, 0.44, 160.0),
    ("CRWD", "CrowdStrike", "CS", 0.28, 0.42, 340.0),
    ("SMCI", "Super Micro Computer", "CS", 0.05, 0.70, 45.0),
    ("SOFI", "SoFi Technologies", "CS", 0.08, 0.55, 8.5),
    ("PLTR", "Palantir", "CS", 0.45, 0.50, 28.0),
    # some deliberately weak / downtrending names (should score low, fail trend)
    ("PFE", "Pfizer", "CS", -0.18, 0.24, 28.0),
    ("INTC", "Intel Corp", "CS", -0.30, 0.38, 31.0),
    ("NKE", "Nike", "CS", -0.22, 0.28, 92.0),
    ("PYPL", "PayPal", "CS", -0.10, 0.34, 62.0),
    ("WBA", "Walgreens", "CS", -0.40, 0.42, 12.0),
    ("MMM", "3M Co", "CS", -0.05, 0.22, 98.0),
    ("T", "AT&T", "CS", 0.02, 0.18, 19.0),
    # low-priced / illiquid-ish names to exercise gates
    ("PENNY", "Penny Co", "CS", 0.0, 0.9, 3.2),
    ("THINL", "Thinly Traded Inc", "CS", 0.05, 0.4, 22.0),
]

_SECTOR = {
    "SPY": "Index", "NVDA": "Technology", "META": "Communication",
    "AVGO": "Technology", "AAPL": "Technology", "MSFT": "Technology",
    "AMZN": "Consumer Disc.", "GOOGL": "Communication", "LLY": "Healthcare",
    "COST": "Consumer Staples", "JPM": "Financials", "XOM": "Energy",
    "WMT": "Consumer Staples", "PANW": "Technology", "UBER": "Technology",
    "SHOP": "Technology", "AMD": "Technology", "CRWD": "Technology",
    "SMCI": "Technology", "SOFI": "Financials", "PLTR": "Technology",
    "PFE": "Healthcare", "INTC": "Technology", "NKE": "Consumer Disc.",
    "PYPL": "Financials", "WBA": "Consumer Staples", "MMM": "Industrials",
    "T": "Communication", "PENNY": "Consumer Disc.", "THINL": "Industrials",
}

_TRADING_DAYS = 300


class SyntheticProvider(PriceProvider, FundamentalProvider):
    name = "synthetic"

    def __init__(self, seed: int = 42):
        self._rng = np.random.default_rng(seed)
        self._hist: dict[str, pd.DataFrame] = {}
        self._build()

    def _build(self) -> None:
        # business-day index ending "today-ish" (fixed span; dates are illustrative)
        idx = pd.bdate_range(end=pd.Timestamp("2026-07-02"), periods=_TRADING_DAYS)
        for tk, _name, _t, drift, vol, p0 in _SPEC:
            mu = drift / 252.0
            sig = vol / np.sqrt(252.0)
            shocks = self._rng.normal(mu, sig, size=_TRADING_DAYS)
            close = p0 * np.exp(np.cumsum(shocks))
            # intraday range around close
            hi = close * (1 + np.abs(self._rng.normal(0, sig / 2, _TRADING_DAYS)))
            lo = close * (1 - np.abs(self._rng.normal(0, sig / 2, _TRADING_DAYS)))
            open_ = np.concatenate([[close[0]], close[:-1]])
            base_vol = 3_000_000 if tk not in ("THINL", "PENNY") else 120_000
            volume = self._rng.integers(base_vol // 2, base_vol * 2, _TRADING_DAYS)
            df = pd.DataFrame(
                {"open": open_, "high": hi, "low": lo, "close": close, "volume": volume},
                index=idx,
            )
            self._hist[tk] = df

    # --- PriceProvider ---
    def get_universe(self) -> list[TickerMeta]:
        return [
            TickerMeta(tk, name, t, "XNAS", _SECTOR.get(tk, "—"))
            for tk, name, t, *_ in _SPEC
        ]

    def get_history(self, tickers: list[str], days: int) -> dict[str, pd.DataFrame]:
        out = {}
        for tk in tickers:
            if tk in self._hist:
                out[tk] = self._hist[tk].iloc[-days:].copy()
        return out

    # --- FundamentalProvider ---
    def get_earnings(self, tickers: list[str]) -> dict[str, Earnings]:
        out = {}
        for tk in tickers:
            # deterministic pseudo values from a per-ticker RNG
            r = np.random.default_rng(abs(hash(tk)) % (2**32))
            days_until = int(r.integers(1, 60))
            surprise = float(r.normal(0.03, 0.08))  # avg small positive drift
            out[tk] = Earnings(
                next_date=str((pd.Timestamp("2026-07-06") + pd.Timedelta(days=days_until)).date()),
                days_until=days_until,
                last_surprise_pct=round(surprise, 4),
            )
        return out

    def get_recommendation(self, ticker: str) -> Recommendation:
        r = np.random.default_rng(abs(hash("rec" + ticker)) % (2**32))
        return Recommendation(trend_score=round(float(r.normal(0.1, 0.4)), 3))

    def get_financials(self, ticker: str) -> Financials:
        r = np.random.default_rng(abs(hash("fin" + ticker)) % (2**32))
        return Financials(
            debt_to_equity=round(float(abs(r.normal(0.8, 0.6))), 2),
            gross_margin=round(float(r.uniform(0.15, 0.65)), 3),
        )
