"""Momentum factor — the primary alpha.

Blended multi-lookback total return, measured as EXCESS over the benchmark
(relative strength), plus proximity to the 52-week high. The blended-excess
metric is ranked cross-sectionally into a 0..1 percentile in scoring.py.
"""
from __future__ import annotations

import pandas as pd

from ..indicators import clamp01, pct_from_52w_high, total_return


def raw_momentum(close: pd.Series, bench_close: pd.Series, cfg: dict) -> float:
    """Blended excess return vs benchmark across configured lookbacks."""
    lbs = cfg["factors"]["momentum"]["lookbacks_days"]
    ws = cfg["factors"]["momentum"]["lookback_weights"]
    total = 0.0
    wsum = 0.0
    for lb, w in zip(lbs, ws):
        r = total_return(close, lb)
        b = total_return(bench_close, lb)
        if r != r or b != b:  # NaN guard
            continue
        total += w * (r - b)
        wsum += w
    return total / wsum if wsum else float("nan")


def high_proximity01(close: pd.Series, tol: float = 0.25) -> float:
    """1.0 at the 52w high, 0.0 once `tol` (e.g. 25%) or more below it."""
    p = pct_from_52w_high(close)  # <= 0
    if p != p:
        return 0.0
    return clamp01(1.0 - (-p) / tol)
