"""Entry playbooks — two tagged setups per name.

The engine used to have a single timing trigger (continuation). This adds a
second, earlier setup so we also catch turns before a continuation confirms:

- Continuation: established uptrend, 20/50 EMA cross / pullback with an RSI band
  (the existing `trigger_eval`). Wider ATR stop.
- Early reversal: fast 5/9 EMA cross up + RSI turning up from oversold + price
  reclaiming the 50-MA from below (200-MA reclaim flagged). Tighter ATR stop —
  earlier entry means more false signals, so risk is cut on the downside.

A name can qualify for both. The composite trigger factor takes the better of the
two scores; the primary tag prefers continuation (confirmed) and falls back to
reversal (early). Framing: configurable screening rules, not advice.
"""
from __future__ import annotations

import pandas as pd

from ..indicators import ema, rsi
from .trigger import trigger_eval


def _reversal(df: pd.DataFrame, cfg: dict) -> tuple[float, dict]:
    p = cfg["playbooks"]["reversal"]
    close = df["close"]
    fast = ema(close, p["ema_fast"])
    slow = ema(close, p["ema_slow"])
    lb = p["cross_lookback"]
    rl = p["reclaim_lookback"]

    # fast>slow cross up within `cross_lookback` bars
    above = fast > slow
    cross_up = bool(above.iloc[-1] and not above.iloc[-lb - 1 : -1].all())

    # RSI lifting off oversold: recently dipped below the floor, now back above it
    # and ticking up.
    rv = rsi(close, cfg["factors"]["trigger"]["rsi_period"])
    r_now = float(rv.iloc[-1])
    recently_oversold = bool(rv.iloc[-rl:].min() < p["rsi_oversold"])
    rsi_turning = bool(recently_oversold and r_now > p["rsi_oversold"] and r_now > float(rv.iloc[-2]))

    # price reclaiming a moving average from below (was under it recently, now over)
    price = float(close.iloc[-1])

    def reclaimed(ma_n: int) -> bool:
        ma = ema(close, ma_n)
        was_below = bool((close.iloc[-rl:-1].values < ma.iloc[-rl:-1].values).any())
        return bool(price > float(ma.iloc[-1]) and was_below)

    reclaimed_50 = reclaimed(p["reclaim_ma"])
    reclaimed_200 = reclaimed(p["flag_ma"])

    passed = bool(cross_up and rsi_turning and reclaimed_50)
    score = 0.0
    if cross_up:
        score += 0.5
    if rsi_turning:
        score += 0.3
    if reclaimed_50:
        score += 0.2
    if reclaimed_200:
        score += 0.1
    score = min(1.0, score)
    if not passed:
        score *= 0.5  # partial setups get partial credit, never a full trigger

    state = "reversal" if passed else ("forming" if (cross_up or rsi_turning) else "none")
    detail = {
        "state": state,
        "cross_up": cross_up,
        "rsi_turning": rsi_turning,
        "reclaimed_50": reclaimed_50,
        "reclaimed_200": reclaimed_200,
        "rsi": round(r_now, 1),
        "passed": passed,
    }
    return float(score), detail


def evaluate_playbooks(df: pd.DataFrame, cfg: dict) -> dict:
    """Evaluate both entry setups and tag the name.

    Returns the trigger factor inputs (best-of-both) plus per-playbook detail so
    each opportunity list can rank on its own logic and show its own stop.
    """
    c_score, c_detail = trigger_eval(df, cfg)   # continuation
    r_score, r_detail = _reversal(df, cfg)       # early reversal

    playbooks: list[str] = []
    if c_detail["passed"]:
        playbooks.append("continuation")
    if r_detail["passed"]:
        playbooks.append("reversal")
    # Primary prefers the confirmed continuation; reversal is the earlier fallback.
    primary = "continuation" if "continuation" in playbooks else (
        "reversal" if "reversal" in playbooks else None
    )

    return {
        "trigger_score": float(max(c_score, r_score)),
        "trigger_passed": bool(playbooks),
        "trigger_detail": c_detail,          # continuation stays the canonical trigger detail
        "reversal_detail": r_detail,
        "playbook": primary,
        "playbooks": playbooks,
        "continuation_score": round(float(c_score), 3),
        "reversal_score": round(float(r_score), 3),
    }
