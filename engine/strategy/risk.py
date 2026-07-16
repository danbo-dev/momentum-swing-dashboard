"""Risk & sizing — ATR stop, R-multiple target, reward:risk, share sizing."""
from __future__ import annotations

import pandas as pd

from ..indicators import atr


def risk_eval(df: pd.DataFrame, cfg: dict, stop_mult: float | None = None) -> dict:
    r = cfg["risk"]
    acct = cfg["account"]
    close = df["close"]
    entry = float(close.iloc[-1])
    a = float(atr(df["high"], df["low"], close, r["atr_period"]).iloc[-1])

    # per-playbook stop width (reversal entries stop tighter); default = continuation
    mult = r["atr_stop_mult"] if stop_mult is None else stop_mult
    stop = entry - mult * a
    risk_per_share = max(entry - stop, 1e-9)
    target = entry + r["target_r_multiple"] * risk_per_share
    reward_risk = (target - entry) / risk_per_share

    # position sizing: risk_per_trade_pct of capital / risk_per_share, capped by budget
    dollar_risk = acct["capital"] * acct["risk_per_trade_pct"] / 100.0
    shares_by_risk = dollar_risk / risk_per_share
    shares_by_budget = acct["max_budget_per_trade"] / entry
    shares = max(0.0, min(shares_by_risk, shares_by_budget))

    return {
        "entry": round(entry, 2),
        "atr": round(a, 3),
        "atr_stop_mult": round(float(mult), 2),
        "stop": round(stop, 2),
        "target": round(target, 2),
        "risk_per_share": round(risk_per_share, 3),
        "reward_risk": round(float(reward_risk), 2),
        "stop_pct": round((entry - stop) / entry * 100, 2),
        "target_pct": round((target - entry) / entry * 100, 2),
        "suggested_shares": round(shares, 2),
        "suggested_dollars": round(shares * entry, 2),
    }
