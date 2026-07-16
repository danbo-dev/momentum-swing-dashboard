"""Exit signals for held positions — traffic-light grading.

Ported and completed from the old positions.py calculate_exit_signals. Unlike
the old dashboard (which rendered only 3 of 4), ALL FOUR signals are returned:
trailing stop, EMA cross, momentum-target, and RSI overbought.
"""
from __future__ import annotations

import pandas as pd

from ..indicators import atr, ema, rsi


def _grade(color: str, label: str) -> dict:
    return {"color": color, "label": label}


def exit_signals(df: pd.DataFrame, entry_price: float, high_watermark: float, cfg: dict) -> dict:
    close = df["close"]
    price = float(close.iloc[-1])
    r = cfg["risk"]
    t = cfg["factors"]["trigger"]

    # 1) trailing stop off the high watermark
    hw = max(high_watermark, price)
    ts_level = hw * (1 - r["trailing_stop_pct"] / 100.0)
    cushion = (price - ts_level) / price * 100
    if price <= ts_level:
        ts = _grade("red", "STOP HIT")
    elif cushion < 3:
        ts = _grade("orange", "Near stop")
    elif cushion < 7:
        ts = _grade("yellow", "Watch stop")
    else:
        ts = _grade("green", "Healthy cushion")
    ts["cushion_pct"] = round(float(cushion), 2)
    ts["level"] = round(float(ts_level), 2)

    # 2) EMA cross exit (fast crossing below slow)
    fast = ema(close, t["ema_fast"]).iloc[-1]
    slow = ema(close, t["ema_slow"]).iloc[-1]
    gap = (fast - slow) / slow * 100
    if gap < 0:
        ema_x = _grade("red", "Bearish cross")
    elif gap < 1:
        ema_x = _grade("orange", "Cross imminent")
    elif gap < 3:
        ema_x = _grade("yellow", "Gap narrowing")
    else:
        ema_x = _grade("green", "Healthy gap")
    ema_x["gap_pct"] = round(float(gap), 2)

    # 3) profit target (R-multiple from entry) — momentum names run, so trail it
    a = float(atr(df["high"], df["low"], close, r["atr_period"]).iloc[-1])
    stop0 = entry_price - r["atr_stop_mult"] * a
    target = entry_price + r["target_r_multiple"] * max(entry_price - stop0, 1e-9)
    prog = (price - entry_price) / max(target - entry_price, 1e-9)
    if price >= target:
        tgt = _grade("red", "Target hit — take profits")
    elif prog > 0.7:
        tgt = _grade("orange", "Approaching target")
    elif prog > 0.3:
        tgt = _grade("yellow", "In progress")
    else:
        tgt = _grade("green", "Room to run")
    tgt["progress_pct"] = round(float(prog * 100), 1)
    tgt["target"] = round(float(target), 2)

    # 4) RSI overbought
    rv = float(rsi(close, t["rsi_period"]).iloc[-1])
    if rv >= 80:
        rsi_sig = _grade("red", "Very overbought")
    elif rv >= 70:
        rsi_sig = _grade("orange", "Overbought")
    elif rv >= 60:
        rsi_sig = _grade("yellow", "Elevated")
    else:
        rsi_sig = _grade("green", "Neutral")
    rsi_sig["rsi"] = round(rv, 1)

    signals = {"trailing_stop": ts, "ema_cross": ema_x, "target": tgt, "rsi": rsi_sig}
    reds = sum(1 for s in signals.values() if s["color"] == "red")
    oranges = sum(1 for s in signals.values() if s["color"] == "orange")
    if reds >= 2:
        urgency = _grade("red", "SELL")
    elif reds == 1 or oranges >= 2:
        urgency = _grade("orange", "Consider selling")
    elif oranges == 1:
        urgency = _grade("yellow", "Watch closely")
    else:
        urgency = _grade("green", "Hold")

    return {
        "price": round(price, 2),
        "signals": signals,
        "urgency": urgency,
        "pnl_pct": round((price - entry_price) / entry_price * 100, 2),
    }
