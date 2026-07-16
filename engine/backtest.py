"""Walk-forward, cost-aware backtest of the PRICE-based score.

Reconstructs momentum + trend + trigger as-of each past rebalance date (the
part we can rebuild from OHLCV alone — point-in-time fundamentals are not on
free tiers), ranks names cross-sectionally, and measures the forward
`horizon_days` return per score quantile, net of `cost_bps`.

Reported: quantile forward-return table, average rank IC (score vs forward
return), long-top / short-bottom spread, and a non-overlapping top-quantile
equity curve. This is the empirical check on whether the score has edge.

Usage:  python -m engine.backtest   ->  data/backtest.json
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .config import load_config
from .data import get_price_provider
from .strategy.momentum import raw_momentum
from .strategy.trend import trend_score
from .strategy.trigger import trigger_eval

REPO_ROOT = Path(__file__).resolve().parents[1]
WARMUP = 130  # bars before first rebalance (allows 63/126d momentum lookbacks)
STEP = 5      # rebalance cadence in trading days


def run_backtest() -> dict:
    cfg = load_config()
    bt = cfg["backtest"]
    h = bt["horizon_days"]
    cost = bt["cost_bps"] / 10000.0
    benchmark = cfg["market_regime"]["benchmark"]

    price = get_price_provider()
    metas = price.get_universe()
    allowed = set(cfg["universe"]["types"])
    tickers = [m.ticker for m in metas if m.type in allowed]
    lim = cfg["universe"].get("limit")
    if lim:
        tickers = tickers[:lim]
    if benchmark not in tickers:
        tickers.append(benchmark)

    hist = price.get_history(tickers, cfg["data"]["history_days"])
    bench_close = hist[benchmark]["close"]
    dates = bench_close.index

    fw = cfg["factors"]
    wm, wt, wg = fw["momentum"]["weight"], fw["trend"]["weight"], fw["trigger"]["weight"]

    records: list[dict] = []
    curve_points: list[dict] = []
    last_curve_i = -(10**9)

    for i in range(WARMUP, len(dates) - h, STEP):
        t = dates[i]
        t_fwd = dates[i + h]
        b_slice = bench_close[bench_close.index <= t]

        raws, absol = {}, {}
        for tk in tickers:
            if tk == benchmark:
                continue
            df = hist.get(tk)
            if df is None:
                continue
            d = df[df.index <= t]
            if len(d) < 65:
                continue
            rm = raw_momentum(d["close"], b_slice, cfg)
            if rm != rm:  # NaN
                continue
            ts, _ = trend_score(d, cfg)
            gs, _ = trigger_eval(d, cfg)
            raws[tk] = rm
            absol[tk] = (ts, gs)

        if len(raws) < bt["min_names_per_day"]:
            continue

        mom_pct = pd.Series(raws).rank(pct=True)
        rows = []
        for tk, rm in raws.items():
            ts, gs = absol[tk]
            score = (wm * mom_pct[tk] + wt * ts + wg * gs) / (wm + wt + wg)
            dfk = hist[tk]
            if t not in dfk.index or t_fwd not in dfk.index:
                continue
            p0 = float(dfk["close"].loc[t])
            p1 = float(dfk["close"].loc[t_fwd])
            if not (p0 > 0) or p1 != p1:  # skip non-positive/NaN base or NaN forward price
                continue
            fwd = (p1 / p0 - 1) - cost
            rows.append({"date": str(t.date()), "ticker": tk, "score": score, "fwd": fwd})
        if len(rows) < bt["min_names_per_day"]:
            continue
        records.extend(rows)

        # non-overlapping top-quantile equity point
        if i - last_curve_i >= h:
            rf = pd.DataFrame(rows)
            top = rf[rf["score"] >= rf["score"].quantile(0.8)]
            curve_points.append({"date": str(t.date()), "ret": float(top["fwd"].mean())})
            last_curve_i = i

    if not records:
        return {"error": "insufficient data for backtest", "records": 0}

    df = pd.DataFrame(records)

    # cross-sectional quantile buckets per date, then aggregate
    n_buckets = 5
    def _bucket(s: pd.Series) -> pd.Series:
        try:
            return pd.qcut(s.rank(method="first"), n_buckets, labels=False)
        except ValueError:
            return pd.cut(s, n_buckets, labels=False)

    df["bucket"] = df.groupby("date")["score"].transform(_bucket)
    table = (
        df.groupby("bucket")
        .agg(avg_fwd_ret=("fwd", "mean"), win_rate=("fwd", lambda s: float((s > 0).mean())),
             count=("fwd", "size"))
        .reset_index()
    )
    quantiles = [
        {
            "quantile": int(r.bucket) + 1,
            "avg_fwd_ret_pct": round(r.avg_fwd_ret * 100, 3),
            "win_rate_pct": round(r.win_rate * 100, 1),
            "n": int(r.count),
        }
        for r in table.itertuples()
    ]

    # average rank IC (Spearman) of score vs forward return, per date
    ics = []
    for _, g in df.groupby("date"):
        if len(g) >= 8:
            # Spearman == Pearson on ranks (avoids a scipy dependency)
            ics.append(g["score"].rank().corr(g["fwd"].rank()))
    mean_ic = float(np.nanmean(ics)) if ics else float("nan")

    top_ret = quantiles[-1]["avg_fwd_ret_pct"] if quantiles else 0.0
    bot_ret = quantiles[0]["avg_fwd_ret_pct"] if quantiles else 0.0

    # chain the non-overlapping top-quantile curve
    equity, val = [], 1.0
    for p in curve_points:
        val *= (1 + p["ret"])
        equity.append({"date": p["date"], "equity": round(val, 4)})

    return {
        "params": {"horizon_days": h, "cost_bps": bt["cost_bps"], "rebalance_step": STEP,
                   "warmup": WARMUP, "n_buckets": n_buckets},
        "provider": price.name,
        "n_observations": int(len(df)),
        "quantiles": quantiles,
        "long_short_spread_pct": round(top_ret - bot_ret, 3),
        "mean_rank_ic": round(mean_ic, 4),
        "top_quantile_equity_curve": equity,
        "verdict": _verdict(mean_ic, top_ret - bot_ret),
    }


def _verdict(ic: float, spread: float) -> str:
    if ic != ic:
        return "inconclusive"
    if ic > 0.03 and spread > 0:
        return "positive_edge"
    if ic > 0:
        return "weak_positive"
    return "no_edge"


def _finite(obj):
    """Recursively replace non-finite floats (inf/NaN) with None. The browser's
    JSON.parse rejects the `Infinity`/`NaN` tokens Python emits by default, which
    would break the dashboard; None (null) is valid and renders as a gap."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _finite(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_finite(v) for v in obj]
    return obj


def main() -> int:
    res = run_backtest()
    out = REPO_ROOT / "web" / "public" / "data" / "backtest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    # allow_nan=False asserts the sanitizer caught everything (else it raises loudly)
    out.write_text(json.dumps(_finite(res), indent=2, allow_nan=False))
    if "error" in res:
        print(f"[backtest] {res['error']}")
    else:
        print(
            f"[backtest] provider={res['provider']} obs={res['n_observations']} "
            f"IC={res['mean_rank_ic']} spread={res['long_short_spread_pct']}% "
            f"verdict={res['verdict']} -> {out}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
