"""Timing trigger — horizon-matched entry timing (replaces the fast 5/9 cross).

A setup 'triggers' when EITHER:
  - a fast>slow EMA cross occurred within `cross_lookback` bars, OR
  - price is pulling back to / just reclaiming a rising fast EMA,
with RSI inside a healthy band (not oversold-broken, not overbought).
"""
from __future__ import annotations

import pandas as pd

from ..indicators import ema, rsi


def trigger_eval(df: pd.DataFrame, cfg: dict) -> tuple[float, dict]:
    t = cfg["factors"]["trigger"]
    close = df["close"]
    fast = ema(close, t["ema_fast"])
    slow = ema(close, t["ema_slow"])
    r = rsi(close, t["rsi_period"]).iloc[-1]

    lookback = t["cross_lookback"]
    above = fast > slow
    # fresh cross: was below within lookback, now above
    recent_cross = bool(above.iloc[-1] and not above.iloc[-lookback - 1 : -1].all())

    fast_rising = len(fast) > 5 and fast.iloc[-1] > fast.iloc[-6]
    dist_to_fast = (close.iloc[-1] - fast.iloc[-1]) / fast.iloc[-1]
    # pullback: price within ~2% above a rising fast EMA and above slow
    pullback = bool(fast_rising and above.iloc[-1] and 0 <= dist_to_fast <= 0.02)

    rsi_ok = bool(t["rsi_floor"] <= r <= t["rsi_ceiling"])
    passed = bool((recent_cross or pullback) and rsi_ok)

    score = 0.0
    if recent_cross:
        score += 0.6
    if pullback:
        score += 0.4
    if rsi_ok:
        score += 0.2
    else:
        score *= 0.5  # penalize bad RSI location

    if recent_cross:
        state = "fresh_cross"
    elif pullback:
        state = "pullback_to_ema"
    elif above.iloc[-1]:
        state = "extended_above"
    else:
        state = "below"

    detail = {
        "state": state,
        "recent_cross": recent_cross,
        "pullback": pullback,
        "rsi": round(float(r), 1),
        "rsi_ok": rsi_ok,
        "passed": passed,
    }
    return float(min(1.0, score)), detail
