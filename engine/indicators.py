"""Technical indicators. Vectorized pandas/numpy; each takes/returns Series.

Ported and extended from the previous scanner.py (compute_rsi, compute_macd,
EMA helpers) with ATR and momentum helpers added for the new strategy.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder RSI (matches the old scanner's ewm(com=period-1) smoothing)."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(100.0)  # no losses => RSI 100


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(com=period - 1, adjust=False).mean()


def total_return(close: pd.Series, lookback: int) -> float:
    """Simple total return over `lookback` bars ending at the last bar."""
    if len(close) <= lookback:
        return float("nan")
    past = close.iloc[-lookback - 1]
    now = close.iloc[-1]
    if past <= 0 or np.isnan(past):
        return float("nan")
    return float(now / past - 1.0)


def pct_from_52w_high(close: pd.Series, window: int = 252) -> float:
    """0 at the high, negative below it (e.g. -0.08 = 8% below the high)."""
    w = close.iloc[-window:] if len(close) >= window else close
    hi = w.max()
    if hi <= 0 or np.isnan(hi):
        return float("nan")
    return float(close.iloc[-1] / hi - 1.0)


def dollar_volume(close: pd.Series, volume: pd.Series, window: int = 20) -> float:
    dv = (close * volume).iloc[-window:]
    return float(dv.median()) if len(dv) else float("nan")


def clamp01(x: float) -> float:
    if np.isnan(x):
        return 0.0
    return float(min(1.0, max(0.0, x)))
