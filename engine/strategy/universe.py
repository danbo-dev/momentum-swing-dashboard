"""Universe gates (hard filters) + market-regime detection."""
from __future__ import annotations

import pandas as pd

from ..data.base import Financials, TickerMeta
from ..indicators import dollar_volume, ema


def passes_liquidity(df: pd.DataFrame, cfg: dict) -> tuple[bool, str]:
    g = cfg["gates"]["liquidity"]
    if not g["enabled"]:
        return True, ""
    if len(df) < g["min_history_days"]:
        return False, "insufficient_history"
    price = float(df["close"].iloc[-1])
    if price < g["min_price"]:
        return False, "price_below_min"
    dv = dollar_volume(df["close"], df["volume"])
    if dv < g["min_avg_dollar_volume"]:
        return False, "illiquid"
    return True, ""


def passes_quality(fin: Financials | None, cfg: dict) -> tuple[bool, str]:
    g = cfg["gates"]["quality"]
    if not g["enabled"] or fin is None:
        return True, ""  # missing data => do not reject
    if fin.debt_to_equity is not None and fin.debt_to_equity > g["max_debt_to_equity"]:
        return False, "over_levered"
    if (
        g["require_positive_gross_margin"]
        and fin.gross_margin is not None
        and fin.gross_margin <= 0
    ):
        return False, "negative_gross_margin"
    return True, ""


def name_excluded(meta: TickerMeta, cfg: dict) -> bool:
    patterns = cfg["universe"]["exclude_name_patterns"]
    up = meta.name.upper()
    return any(p.upper() in up for p in patterns)


def market_regime(bench_df: pd.DataFrame, cfg: dict) -> dict:
    """Risk-on when the benchmark is above its long MA."""
    ma_n = cfg["market_regime"]["ma"]
    close = bench_df["close"]
    ma = ema(close, ma_n)
    price = float(close.iloc[-1])
    ma_now = float(ma.iloc[-1])
    risk_on = price > ma_now
    ma_rising = len(ma) > 21 and ma.iloc[-1] > ma.iloc[-22]
    return {
        "risk_on": bool(risk_on),
        "benchmark": cfg["market_regime"]["benchmark"],
        "price": round(price, 2),
        "ma": round(ma_now, 2),
        "ma_rising": bool(ma_rising),
        "label": "Risk-On" if risk_on else "Risk-Off",
    }
