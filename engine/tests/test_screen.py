"""Unit tests for the broad-universe screen (Stages 1-2), no network."""
import pandas as pd

from engine.strategy.screen import screen_universe

DATES = pd.bdate_range("2024-01-01", periods=30)


def _series(ticker, start, end, vol, bars=30):
    """A linear price ramp start->end over `bars` trailing days, constant volume."""
    dates = DATES[-bars:]
    prices = [start + (end - start) * i / (bars - 1) for i in range(bars)]
    return pd.DataFrame({
        "ticker": ticker, "date": dates,
        "open": prices, "high": prices, "low": prices, "close": prices,
        "volume": vol,
    })


def _frame():
    parts = [
        _series("SPY", 100, 103, 1_000_000),    # benchmark, +3%
        _series("WIN1", 50, 65, 2_000_000),     # +30%, liquid
        _series("WIN2", 20, 24, 5_000_000),     # +20%, liquid
        _series("FLAT", 40, 40, 3_000_000),     # 0%
        _series("LOSE", 30, 24, 3_000_000),     # -20%
        _series("PENNY", 2, 3, 5_000_000),      # price below band
        _series("THIN", 100, 110, 100),         # dollar volume below floor
        _series("NEW", 40, 55, 3_000_000, bars=5),   # too few bars
        _series("NOTBASE", 40, 80, 3_000_000),  # strong but not in base list
    ]
    return pd.concat(parts, ignore_index=True)


BASE = {"SPY", "WIN1", "WIN2", "FLAT", "LOSE", "PENNY", "THIN", "NEW"}


def _cfg(**over):
    f = {
        "price_band": [5, 500], "min_dollar_volume": 1_000_000,
        "min_screen_bars": 20, "momentum_short_window": 10,
        "momentum_rank_keep": 1.0, "max_bucket": 100,
    }
    f.update(over)
    return {"funnel": f}


def test_stage1_filters_drop_penny_thin_new_and_nonbase():
    bucket, stats = screen_universe(_frame(), BASE, "SPY", _cfg())
    assert "PENNY" not in bucket   # price below band
    assert "THIN" not in bucket    # illiquid
    assert "NEW" not in bucket     # insufficient bars
    assert "NOTBASE" not in bucket # not in base list
    assert {"WIN1", "WIN2", "FLAT", "LOSE"} <= set(bucket)
    assert stats["base"] == len(BASE)
    assert stats["screened"] == len(bucket)  # keep_frac=1.0 => bucket == stage1


def test_stage2_ranks_by_relative_strength():
    bucket, _ = screen_universe(_frame(), BASE, "SPY", _cfg())
    # WIN1 (+30%) outranks WIN2 (+20%) outranks FLAT outranks LOSE
    order = [t for t in bucket if t in {"WIN1", "WIN2", "FLAT", "LOSE"}]
    assert order == ["WIN1", "WIN2", "FLAT", "LOSE"]


def test_momentum_rank_keep_drops_laggards():
    bucket, _ = screen_universe(_frame(), BASE, "SPY", _cfg(momentum_rank_keep=0.4))
    assert "WIN1" in bucket
    assert "LOSE" not in bucket    # bottom of the momentum rank, dropped


def test_max_bucket_backstop_caps_and_flags():
    bucket, stats = screen_universe(_frame(), BASE, "SPY", _cfg(max_bucket=2))
    assert stats["capped_by_max_bucket"] is True
    assert len(bucket) == 2
    assert stats["momentum_pct_floor"] is not None


def test_force_include_keeps_held_laggard():
    bucket, _ = screen_universe(
        _frame(), BASE, "SPY", _cfg(momentum_rank_keep=0.2), force_include={"LOSE"}
    )
    assert "LOSE" in bucket        # held position kept despite weak momentum


def test_empty_frame_is_safe():
    bucket, stats = screen_universe(pd.DataFrame(), BASE, "SPY", _cfg())
    assert bucket == []
    assert stats["bucket"] == 0


LONG_DATES = pd.bdate_range("2024-01-01", periods=90)


def _long(ticker, prices, vol=3_000_000):
    return pd.DataFrame({
        "ticker": ticker, "date": LONG_DATES,
        "open": prices, "high": prices, "low": prices, "close": prices, "volume": vol,
    })


def test_reversal_lane_admits_50ma_reclaim():
    import numpy as np
    # SPY flat benchmark; MOVER = strong momentum (makes the bucket);
    # RECL = long decline then a fresh pop back above its 50-MA (low momentum).
    spy = _long("SPY", np.linspace(100, 103, 90))
    mover = _long("MOVER", np.linspace(40, 80, 90))
    recl_prices = np.concatenate([np.linspace(80, 55, 80), np.linspace(56, 64, 10)])
    recl = _long("RECL", recl_prices)
    frame = pd.concat([spy, mover, recl], ignore_index=True)
    base = {"SPY", "MOVER", "RECL"}

    # momentum-only: RECL (negative momentum) is ranked out
    keep_only, _ = screen_universe(frame, base, "SPY", _cfg(momentum_rank_keep=0.34, reversal_lane=False), )
    assert "RECL" not in keep_only

    # with the reversal lane on, the 50-MA reclaim is admitted anyway
    over = {"momentum_rank_keep": 0.34, "reversal_lane": True, "reversal_lane_ma": 50,
            "reversal_lane_lookback": 10, "reversal_lane_band": 0.15, "reversal_lane_max": 10}
    bucket, stats = screen_universe(frame, base, "SPY", _cfg(**over))
    assert "RECL" in bucket
    assert stats["reversal_added"] >= 1
