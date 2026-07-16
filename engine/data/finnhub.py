"""Finnhub free-tier fundamentals provider: earnings + recommendations + metrics.

Free tier: 60 calls/min. Provides earnings calendar, recommendation trends,
EPS surprises and basic financials. NOTE: Finnhub's historical price candles
are premium on free — do NOT use this for OHLCV (use Polygon/Tiingo).
"""
from __future__ import annotations

from datetime import date, timedelta

from ..config import env, load_config
from .base import Earnings, Financials, FundamentalProvider, Recommendation
from ._http import RateLimiter, cached_get

BASE = "https://finnhub.io/api/v1"


class FinnhubProvider(FundamentalProvider):
    name = "finnhub"

    def __init__(self):
        cfg = load_config()["data"]
        self._key = env("FINNHUB_API_KEY")
        self._limiter = RateLimiter(cfg["finnhub"]["rate_limit_per_min"])
        self._ttl = cfg["cache_ttl_hours"]
        self._today = date.today()

    def _get(self, path: str, params: dict, key: str) -> dict:
        params = {**params, "token": self._key}
        return cached_get(f"{BASE}{path}", params, self._limiter, self._ttl, cache_key=key)

    def get_earnings(self, tickers: list[str]) -> dict[str, Earnings]:
        # one calendar call covers all symbols in the forward window
        frm = self._today
        to = self._today + timedelta(days=120)
        out: dict[str, Earnings] = {}
        try:
            data = self._get(
                "/calendar/earnings",
                {"from": str(frm), "to": str(to)},
                key=f"fh_earn_cal_{frm}",
            )
        except Exception:
            data = {}
        wanted = set(tickers)
        for row in data.get("earningsCalendar", []):
            sym = row.get("symbol")
            if sym not in wanted or sym in out:
                continue
            d = row.get("date")
            days_until = None
            if d:
                try:
                    days_until = (date.fromisoformat(d) - self._today).days
                except ValueError:
                    pass
            out[sym] = Earnings(next_date=d, days_until=days_until)
        # fill surprise per ticker (cheap, cached)
        for tk in tickers:
            e = out.get(tk) or Earnings()
            try:
                hist = self._get("/stock/earnings", {"symbol": tk}, key=f"fh_earn_{tk}")
                if isinstance(hist, list) and hist:
                    latest = hist[0]
                    est, act = latest.get("estimate"), latest.get("actual")
                    if est not in (None, 0) and act is not None:
                        e.last_surprise_pct = round((act - est) / abs(est), 4)
            except Exception:
                pass
            out[tk] = e
        return out

    def get_recommendation(self, ticker: str) -> Recommendation:
        try:
            data = self._get(
                "/stock/recommendation", {"symbol": ticker}, key=f"fh_rec_{ticker}"
            )
        except Exception:
            return Recommendation()
        if not isinstance(data, list) or not data:
            return Recommendation()
        # data[0] is most recent month. Bull ratio now vs ~3 months ago -> trend.
        def bull(row):
            tot = sum(row.get(k, 0) for k in ("strongBuy", "buy", "hold", "sell", "strongSell"))
            if not tot:
                return 0.0
            return (row.get("strongBuy", 0) + row.get("buy", 0)) / tot

        now = bull(data[0])
        prior = bull(data[min(3, len(data) - 1)])
        trend = max(-1.0, min(1.0, (now - 0.5) + (now - prior)))
        return Recommendation(trend_score=round(trend, 3), latest=data[0])

    def get_financials(self, ticker: str) -> Financials:
        try:
            data = self._get(
                "/stock/metric", {"symbol": ticker, "metric": "all"}, key=f"fh_metric_{ticker}"
            )
        except Exception:
            return Financials()
        m = (data or {}).get("metric", {}) or {}
        de = m.get("totalDebt/totalEquityQuarterly") or m.get("longTermDebt/equityQuarterly")
        gm = m.get("grossMarginTTM")
        return Financials(
            debt_to_equity=float(de) if de is not None else None,
            # Finnhub reports margins in percent; store as fraction
            gross_margin=float(gm) / 100.0 if gm is not None else None,
        )

    def get_sector(self, ticker: str) -> str | None:
        """Industry label from the company profile — used to give broad-universe
        names a sector for the heatmap when the price list has none."""
        try:
            data = self._get("/stock/profile2", {"symbol": ticker}, key=f"fh_profile_{ticker}")
        except Exception:
            return None
        return (data or {}).get("finnhubIndustry") or None
