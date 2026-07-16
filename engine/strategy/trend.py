"""Trend factor — reward price above rising long MAs (buy strength).

This is the deliberate inverse of the old 'buy below the 200 EMA' logic.
"""
from __future__ import annotations

import pandas as pd

from ..indicators import ema


def trend_score(df: pd.DataFrame, cfg: dict) -> tuple[float, dict]:
    close = df["close"]
    fast_n = cfg["factors"]["trend"]["ma_fast"]
    slow_n = cfg["factors"]["trend"]["ma_slow"]
    ma_fast = ema(close, fast_n)
    ma_slow = ema(close, slow_n)
    price = close.iloc[-1]
    f = ma_fast.iloc[-1]
    s = ma_slow.iloc[-1]
    # is the slow MA rising? (compare to ~1 month ago)
    slow_rising = len(ma_slow) > 21 and ma_slow.iloc[-1] > ma_slow.iloc[-22]

    score = 0.0
    if price > f:
        score += 0.4
    if price > s:
        score += 0.3
    if f > s:
        score += 0.2
    if slow_rising:
        score += 0.1

    detail = {
        "above_fast_ma": bool(price > f),
        "above_slow_ma": bool(price > s),
        "fast_above_slow": bool(f > s),
        "slow_ma_rising": bool(slow_rising),
        "ma_fast": round(float(f), 2),
        "ma_slow": round(float(s), 2),
    }
    return float(min(1.0, score)), detail
