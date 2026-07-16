"""Polygon.io ("Massive") free-tier price + universe provider.

Free tier: 5 calls/min, EOD only, ~2y history. Universe via the ticker
reference endpoint; history via per-ticker daily aggregates (one call returns a
ticker's whole range). Both are rate-limited and disk-cached. For large
universes on the free tier, set `universe.limit` (or CONTEXT_UNIVERSE_LIMIT).
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from ..config import env, load_config
from .base import PriceProvider, TickerMeta
from ._http import RateLimiter, cached_get

BASE = "https://api.polygon.io"

# Polygon primary_exchange MIC -> our short codes are already MICs (XNYS/XNAS/XASE)
_ETF_TYPES = {"ETF", "ETN", "ETV"}


class PolygonProvider(PriceProvider):
    name = "polygon"

    def __init__(self):
        cfg = load_config()["data"]
        self._key = env("POLYGON_API_KEY")
        self._limiter = RateLimiter(cfg["polygon"]["rate_limit_per_min"])
        self._ttl = cfg["cache_ttl_hours"]

    def get_universe(self) -> list[TickerMeta]:
        full = load_config()["data"]["polygon"]
        if full.get("use_seed_universe", True):
            from .seed_universe import seed_metas

            return seed_metas()
        cfg = load_config()["universe"]
        allowed_ex = set(cfg["exchanges"])
        metas: list[TickerMeta] = []
        url = f"{BASE}/v3/reference/tickers"
        params = {
            "market": "stocks",
            "active": "true",
            "limit": 1000,
            "apiKey": self._key,
        }
        pages = 0
        while url and pages < 30:  # safety cap
            data = cached_get(url, params, self._limiter, self._ttl,
                              cache_key=f"poly_universe_{pages}")
            for r in data.get("results", []):
                ex = r.get("primary_exchange")
                if allowed_ex and ex not in allowed_ex:
                    continue
                raw_type = (r.get("type") or "").upper()
                t = "ETF" if raw_type in _ETF_TYPES else "CS"
                sector = r.get("sic_description") or "—"
                metas.append(
                    TickerMeta(r["ticker"], r.get("name", r["ticker"]), t, ex or "", sector)
                )
            url = data.get("next_url")
            params = {"apiKey": self._key} if url else params
            pages += 1
        return metas

    def get_grouped_daily(self, day: date) -> dict[str, dict]:
        """Whole-market OHLCV for one trading day in a single call.

        Returns {ticker: {open, high, low, close, volume}}; empty dict on a
        non-trading day (weekend/holiday) or before that day's EOD bars land.
        Past dates are immutable so they cache effectively forever.
        """
        url = f"{BASE}/v2/aggs/grouped/locale/us/market/stocks/{day.isoformat()}"
        params = {"adjusted": "true", "apiKey": self._key}
        ttl = self._ttl if day >= date.today() else 24 * 365  # past days never change
        try:
            data = cached_get(url, params, self._limiter, ttl,
                              cache_key=f"poly_grouped_{day.isoformat()}")
        except Exception:
            return {}
        out: dict[str, dict] = {}
        for r in data.get("results", []):
            tk = r.get("T")
            if not tk or r.get("c") is None:
                continue
            out[tk] = {
                "open": r.get("o"), "high": r.get("h"), "low": r.get("l"),
                "close": r.get("c"), "volume": r.get("v", 0),
            }
        return out

    def get_recent_bars(self, days: int) -> pd.DataFrame:
        """Tidy whole-market frame of the last `days` COMPLETED trading days,
        assembled from grouped-daily calls. Columns:
        ticker, date, open, high, low, close, volume.

        Walks back from yesterday (completed sessions only, so both the midday
        and post-close runs see the same EOD frame and no partial bars leak in).
        Weekends are skipped without a call; holidays return empty and are
        skipped too. Steady-state cost is ~1 new grouped call per trading day.
        """
        rows: list[tuple] = []
        d = date.today() - timedelta(days=1)
        seen = 0
        scanned = 0
        while seen < days and scanned < days * 2 + 15:  # calendar pad for weekends/holidays
            scanned += 1
            if d.weekday() < 5:  # Mon-Fri only
                grouped = self.get_grouped_daily(d)
                if grouped:
                    seen += 1
                    for tk, bar in grouped.items():
                        rows.append((tk, d, bar["open"], bar["high"], bar["low"],
                                     bar["close"], bar["volume"]))
            d -= timedelta(days=1)
        return pd.DataFrame(
            rows, columns=["ticker", "date", "open", "high", "low", "close", "volume"]
        )

    def get_history(self, tickers: list[str], days: int) -> dict[str, pd.DataFrame]:
        to = date.today()
        frm = to - timedelta(days=int(days * 1.5) + 10)  # calendar pad for weekends/holidays
        out: dict[str, pd.DataFrame] = {}
        for tk in tickers:
            url = f"{BASE}/v2/aggs/ticker/{tk}/range/1/day/{frm}/{to}"
            params = {"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": self._key}
            try:
                data = cached_get(url, params, self._limiter, self._ttl,
                                  cache_key=f"poly_hist_{tk}_{to}")
            except Exception:
                continue
            res = data.get("results") or []
            if not res:
                continue
            df = pd.DataFrame(res)
            df["date"] = pd.to_datetime(df["t"], unit="ms")
            df = df.set_index("date").rename(
                columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}
            )[["open", "high", "low", "close", "volume"]]
            out[tk] = df.iloc[-days:]
        return out
