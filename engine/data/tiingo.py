"""Tiingo free-tier OHLCV fallback (1,000 req/day). Price history only.

Set `data.price_provider: tiingo` to use this instead of Polygon. Tiingo has no
convenient free universe endpoint, so pair it with a Polygon universe call or a
static list; get_universe here raises to make that explicit.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from ..config import env, load_config
from .base import PriceProvider, TickerMeta
from ._http import RateLimiter, cached_get

BASE = "https://api.tiingo.com/tiingo/daily"


class TiingoProvider(PriceProvider):
    name = "tiingo"

    def __init__(self):
        cfg = load_config()["data"]
        self._key = env("TIINGO_API_KEY")
        self._limiter = RateLimiter(50)  # ~50/hr free; be gentle
        self._ttl = cfg["cache_ttl_hours"]

    def get_universe(self) -> list[TickerMeta]:
        raise NotImplementedError(
            "Tiingo is an OHLCV fallback only. Use Polygon for the universe, or "
            "supply a static ticker list."
        )

    def get_history(self, tickers: list[str], days: int) -> dict[str, pd.DataFrame]:
        to = date.today()
        frm = to - timedelta(days=int(days * 1.5) + 10)
        out: dict[str, pd.DataFrame] = {}
        for tk in tickers:
            url = f"{BASE}/{tk}/prices"
            params = {"startDate": str(frm), "endDate": str(to), "token": self._key}
            try:
                data = cached_get(url, params, self._limiter, self._ttl,
                                  cache_key=f"tiingo_{tk}_{to}")
            except Exception:
                continue
            if not isinstance(data, list) or not data:
                continue
            df = pd.DataFrame(data)
            df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
            # prefer split/dividend-adjusted columns when present
            ren = {
                "adjOpen": "open", "adjHigh": "high", "adjLow": "low",
                "adjClose": "close", "adjVolume": "volume",
            }
            for a, b in ren.items():
                if a not in df.columns:
                    df[a] = df[b]
            df = df.set_index("date").rename(columns=ren)[
                ["open", "high", "low", "close", "volume"]
            ]
            out[tk] = df.iloc[-days:]
        return out
