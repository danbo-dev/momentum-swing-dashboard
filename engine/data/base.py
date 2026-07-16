"""Data types and provider interfaces."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd


@dataclass
class TickerMeta:
    ticker: str
    name: str
    type: str  # "CS" | "ETF"
    exchange: str
    sector: str = "—"


@dataclass
class Earnings:
    next_date: str | None = None
    days_until: int | None = None
    last_surprise_pct: float | None = None  # (actual-estimate)/|estimate|


@dataclass
class Recommendation:
    # -1..+1: positive => improving buy consensus over recent months
    trend_score: float | None = None
    latest: dict | None = None


@dataclass
class Financials:
    debt_to_equity: float | None = None
    gross_margin: float | None = None


class PriceProvider(ABC):
    name: str = "base"

    @abstractmethod
    def get_universe(self) -> list[TickerMeta]:
        ...

    @abstractmethod
    def get_history(self, tickers: list[str], days: int) -> dict[str, pd.DataFrame]:
        """Return {ticker: DataFrame[open,high,low,close,volume]} indexed by date."""
        ...


class FundamentalProvider(ABC):
    name: str = "base"

    @abstractmethod
    def get_earnings(self, tickers: list[str]) -> dict[str, Earnings]:
        ...

    @abstractmethod
    def get_recommendation(self, ticker: str) -> Recommendation:
        ...

    @abstractmethod
    def get_financials(self, ticker: str) -> Financials:
        ...

    def get_sector(self, ticker: str) -> str | None:
        """Best-effort sector/industry label; None if unavailable. Optional —
        used to enrich broad-universe names that lack a curated sector."""
        return None
