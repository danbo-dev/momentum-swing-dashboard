import numpy as np
import pandas as pd

from engine.indicators import atr, clamp01, ema, pct_from_52w_high, rsi, total_return


def _series(vals):
    return pd.Series(vals, dtype="float64")


def test_ema_tracks_constant():
    s = _series([10.0] * 50)
    assert abs(ema(s, 10).iloc[-1] - 10.0) < 1e-9


def test_rsi_bounds_and_uptrend():
    up = _series(np.linspace(10, 30, 60))
    r = rsi(up, 14).iloc[-1]
    assert 0 <= r <= 100
    assert r > 70  # pure uptrend => high RSI


def test_rsi_downtrend_low():
    down = _series(np.linspace(30, 10, 60))
    assert rsi(down, 14).iloc[-1] < 30


def test_atr_positive():
    n = 60
    close = _series(np.linspace(10, 20, n))
    high = close + 0.5
    low = close - 0.5
    a = atr(high, low, close, 14)
    assert (a.dropna() > 0).all()


def test_total_return():
    s = _series([100, 110, 121])  # +10% then +10%
    assert abs(total_return(s, 2) - 0.21) < 1e-9


def test_total_return_insufficient():
    s = _series([100, 110])
    assert np.isnan(total_return(s, 5))


def test_pct_from_high_at_high_is_zero():
    s = _series(np.linspace(10, 20, 300))  # ends at the high
    assert abs(pct_from_52w_high(s)) < 1e-9


def test_clamp01():
    assert clamp01(-5) == 0.0
    assert clamp01(5) == 1.0
    assert clamp01(float("nan")) == 0.0
    assert clamp01(0.4) == 0.4
