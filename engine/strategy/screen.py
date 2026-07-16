"""Cheap whole-market screen — Stage 1 + Stage 2 of the broad-universe funnel.

Given a tidy frame of recent whole-market daily bars (from Polygon grouped-daily,
~1 call/day), narrow the base list to the day's deep-dive *bucket* using only data
we already have — no per-ticker calls. Filters determine the bucket; `max_bucket`
is a rate-limit backstop that raises the momentum threshold (logged), never an
arbitrary top-N slice.

Pure and side-effect-light (one log line when the backstop bites) so it unit-tests
against a synthetic frame with no network.
"""
from __future__ import annotations

import math

import pandas as pd


def screen_universe(
    frame: pd.DataFrame,
    base_tickers: set[str],
    benchmark: str,
    cfg: dict,
    force_include: set[str] | None = None,
) -> tuple[list[str], dict]:
    """Return (bucket_tickers, funnel_stats).

    - frame: columns [ticker, date, open, high, low, close, volume] over the last
      ~N completed trading days for the whole market.
    - base_tickers: the type/exchange/name-filtered base list (Stage 0).
    - benchmark: relative-strength benchmark (e.g. SPY); used for excess return.
    - force_include: tickers to keep in the bucket regardless of screen (held
      positions) — they still need a deep dive.
    """
    f = cfg["funnel"]
    lo, hi = f["price_band"]
    min_dv = f["min_dollar_volume"]
    min_bars = f["min_screen_bars"]
    short_window = f.get("momentum_short_window", 10)
    keep_frac = f["momentum_rank_keep"]
    max_bucket = f["max_bucket"]
    force_include = force_include or set()

    stats = {
        "base": len(base_tickers),
        "grouped_names": 0,
        "screened": 0,
        "bucket": 0,
        "momentum_pct_floor": None,
        "capped_by_max_bucket": False,
    }
    if frame is None or frame.empty:
        return [], stats

    # --- Pivot to wide close / dollar-volume matrices (date x ticker) ---
    wide = frame.pivot_table(index="date", columns="ticker", values="close", aggfunc="last").sort_index()
    dv = frame.assign(_dv=frame["close"] * frame["volume"]).pivot_table(
        index="date", columns="ticker", values="_dv", aggfunc="last"
    ).sort_index()
    stats["grouped_names"] = int(wide.shape[1])

    bars = wide.notna().sum()                 # real presence per ticker
    filled = wide.ffill()
    last = filled.iloc[-1]
    med_dv = dv.median()                      # median dollar volume over the window (NaN-skipping)

    n = len(filled)
    full_ret = filled.iloc[-1] / filled.iloc[0] - 1.0
    k = min(short_window, n - 1)
    short_ret = (filled.iloc[-1] / filled.iloc[-1 - k] - 1.0) if k > 0 else full_ret

    # Excess return vs the benchmark (relative strength), blended long+short.
    bench_full = float(full_ret.get(benchmark, 0.0) or 0.0)
    bench_short = float(short_ret.get(benchmark, 0.0) or 0.0)
    momentum = 0.6 * (full_ret - bench_full) + 0.4 * (short_ret - bench_short)

    screen = pd.DataFrame({
        "last": last, "med_dv": med_dv, "bars": bars, "momentum": momentum,
    })
    # --- Stage 1: cheap price / liquidity / history filters ---
    in_base = screen.index.isin(base_tickers)
    stage1 = screen[
        in_base
        & (screen["bars"] >= min_bars)
        & (screen["last"] >= lo)
        & (screen["last"] <= hi)
        & (screen["med_dv"] >= min_dv)
        & screen["momentum"].notna()
    ].copy()
    stats["screened"] = int(len(stage1))

    # --- Stage 2: momentum rank -> bucket (relative-strength percentile keep) ---
    stage1 = stage1.sort_values("momentum", ascending=False)
    keep_n = max(1, math.ceil(keep_frac * len(stage1))) if len(stage1) else 0
    if max_bucket is not None and keep_n > max_bucket:
        keep_n = max_bucket
        stats["capped_by_max_bucket"] = True
    bucket_rows = stage1.iloc[:keep_n]
    if len(bucket_rows):
        stats["momentum_pct_floor"] = round(float(bucket_rows["momentum"].iloc[-1]) * 100, 2)

    bucket = list(bucket_rows.index)
    bucket_set = set(bucket)

    # --- Reversal lane: admit early-turn candidates the momentum rank drops ---
    # A momentum-ranked bucket is all extended names, so the reversal playbook has
    # no candidates. Cheaply flag Stage-1 survivors reclaiming their 50-MA from
    # below (from the grouped frame we already have) and admit them regardless of
    # momentum rank; the Stage-3 playbook does the precise tagging on full history.
    stats["reversal_candidates"] = 0
    stats["reversal_added"] = 0
    if f.get("reversal_lane"):
        rma = f.get("reversal_lane_ma", 50)
        rlb = f.get("reversal_lane_lookback", 10)
        band = f.get("reversal_lane_band", 0.10)
        ma = filled.rolling(rma).mean()
        ma_now = ma.iloc[-1]
        price_now = filled.iloc[-1]
        was_below = (filled.iloc[-rlb:] < ma.iloc[-rlb:]).any()   # under the MA recently
        dist = (price_now - ma_now) / ma_now
        reclaim = (price_now > ma_now) & was_below & (dist <= band) & ma_now.notna()
        cand = [t for t in stage1.index if bool(reclaim.get(t, False)) and t not in bucket_set]
        stats["reversal_candidates"] = len(cand)
        # rank reclaimers by momentum (prefer the shallower dips) and cap the add
        add = list(stage1.loc[cand].sort_values("momentum", ascending=False)
                   .index[: f.get("reversal_lane_max", 60)])
        stats["reversal_added"] = len(add)
        bucket.extend(add)
        bucket_set.update(add)

    # Force-include held positions that survived to the screen but got ranked out.
    for tk in force_include:
        if tk not in bucket_set and tk in screen.index:
            bucket.append(tk)
    stats["bucket"] = len(bucket)

    if stats["capped_by_max_bucket"]:
        print(
            f"[funnel] max_bucket={max_bucket} reached: raised momentum floor to "
            f"{stats['momentum_pct_floor']}% excess (screened={stats['screened']} "
            f"-> bucket={stats['bucket']})"
        )
    return bucket, stats
