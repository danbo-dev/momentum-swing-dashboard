"""Unit tests for the two entry playbooks (continuation vs early reversal)."""
import numpy as np
import pandas as pd

from engine.config import load_config
from engine.indicators import ema
from engine.strategy.playbooks import evaluate_playbooks
from engine.strategy.risk import risk_eval

CFG = load_config()


def _frame(prices):
    p = np.asarray(prices, dtype=float)
    idx = pd.bdate_range("2023-01-01", periods=len(p))
    return pd.DataFrame(
        {"open": p, "high": p * 1.01, "low": p * 0.99, "close": p, "volume": 1e6}, index=idx
    )


def _uptrend_pullback():
    rng = np.random.default_rng(3)
    up = np.linspace(45, 92, 230) + rng.normal(0, 0.8, 230)
    up[-1] = ema(pd.Series(up), 20).iloc[-1] * 1.01  # land in the pullback band
    return _frame(up)


def _reversal_pattern():
    # long decline -> sharp dip into oversold -> fresh 4-bar pop through the 50-EMA
    rng = np.random.default_rng(1)
    dec = np.linspace(100, 60, 175) + rng.normal(0, 1.3, 175)
    dip = np.linspace(60, 55, 8) + rng.normal(0, 0.3, 8)
    pop = 55 + np.linspace(2.5, 10, 4)
    return _frame(np.concatenate([dec, dip, pop]))


def _downtrend():
    rng = np.random.default_rng(5)
    return _frame(np.linspace(100, 55, 240) + rng.normal(0, 1.0, 240))


def test_continuation_triggers_on_uptrend_pullback():
    r = evaluate_playbooks(_uptrend_pullback(), CFG)
    assert "continuation" in r["playbooks"]
    assert r["playbook"] == "continuation"
    assert r["trigger_passed"] is True


def test_reversal_triggers_on_early_turn():
    r = evaluate_playbooks(_reversal_pattern(), CFG)
    d = r["reversal_detail"]
    assert d["cross_up"] and d["rsi_turning"] and d["reclaimed_50"]
    assert d["passed"] is True
    assert "reversal" in r["playbooks"]
    # not (yet) a continuation setup, so reversal is the primary tag
    assert r["playbook"] == "reversal"


def test_downtrend_triggers_neither():
    r = evaluate_playbooks(_downtrend(), CFG)
    assert r["playbooks"] == []
    assert r["playbook"] is None
    assert r["trigger_passed"] is False


def test_reversal_stop_is_tighter():
    df = _reversal_pattern()
    default = risk_eval(df, CFG)
    reversal = risk_eval(df, CFG, stop_mult=CFG["playbooks"]["reversal"]["atr_stop_mult"])
    assert CFG["playbooks"]["reversal"]["atr_stop_mult"] < CFG["risk"]["atr_stop_mult"]
    # tighter multiplier => smaller stop distance from entry
    assert reversal["stop_pct"] < default["stop_pct"]
    assert reversal["atr_stop_mult"] == CFG["playbooks"]["reversal"]["atr_stop_mult"]
