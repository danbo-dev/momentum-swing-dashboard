"""Scan pipeline: universe -> gates -> features -> score -> results payload.

Gating order is deliberate and rate-limit-friendly: cheap price-only liquidity
gating first, then fundamentals (Finnhub) are fetched ONLY for survivors.
"""
from __future__ import annotations

from .config import load_config
from .data import get_fundamental_provider, get_price_provider
from .indicators import rsi
from .results import build_results, change_pct, spark
from .strategy.catalysts import catalyst_score
from .strategy.momentum import high_proximity01, raw_momentum
from .strategy.positions import exit_signals
from .strategy.risk import risk_eval
from .strategy.playbooks import evaluate_playbooks
from .strategy.scoring import score_all
from .strategy.screen import screen_universe
from .strategy.trend import trend_score
from .strategy.universe import (
    market_regime,
    name_excluded,
    passes_liquidity,
    passes_quality,
)


def run_scan(positions: list[dict] | None = None) -> dict:
    cfg = load_config()
    price = get_price_provider()
    fund = get_fundamental_provider()

    benchmark = cfg["market_regime"]["benchmark"]
    metas = price.get_universe()

    # --- Stage 0: base list — type + name exclusions + optional limit ---
    allowed_types = set(cfg["universe"]["types"])
    metas = [m for m in metas if m.type in allowed_types and not name_excluded(m, cfg)]
    limit = cfg["universe"].get("limit")
    if limit:
        metas = metas[:limit]
    meta_by = {m.ticker: m for m in metas}
    held = {p["ticker"] for p in (positions or []) if p.get("ticker")}

    # --- Stages 1-2: cheap whole-market screen -> deep-dive bucket ---
    # Only when the provider serves grouped-daily and we're not pinned to the
    # curated seed list. Otherwise fall back to deep-diving the whole base list.
    funnel_stats = None
    use_funnel = (
        bool(cfg["data"]["polygon"].get("grouped_daily"))
        and not cfg["data"]["polygon"].get("use_seed_universe", True)
        and hasattr(price, "get_recent_bars")
    )
    if use_funnel:
        frame = price.get_recent_bars(cfg["funnel"]["screen_days"])
        bucket, funnel_stats = screen_universe(
            frame, set(meta_by), benchmark, cfg, force_include=held
        )
        tickers = list(bucket)
    else:
        tickers = [m.ticker for m in metas]

    if benchmark not in tickers:
        tickers.append(benchmark)
    # ensure held-position tickers get history even if outside the screened set
    for tk in held:
        if tk not in tickers:
            tickers.append(tk)

    hist = price.get_history(tickers, cfg["data"]["history_days"])
    if benchmark not in hist:
        raise RuntimeError(f"benchmark {benchmark} missing from price history")
    bench_df = hist[benchmark]
    bench_close = bench_df["close"]
    regime = market_regime(bench_df, cfg)

    # --- Stage A: liquidity gate (price/volume only) ---
    survivors = []
    dropped = {"illiquid": 0, "price_below_min": 0, "insufficient_history": 0, "no_data": 0}
    for tk in tickers:
        if tk == benchmark:
            continue
        df = hist.get(tk)
        if df is None or df.empty:
            dropped["no_data"] += 1
            continue
        ok, reason = passes_liquidity(df, cfg)
        if not ok:
            dropped[reason] = dropped.get(reason, 0) + 1
            continue
        survivors.append(tk)

    # --- Stage B: fundamentals for survivors only ---
    earnings = fund.get_earnings(survivors)
    quality_dropped = 0
    features = []
    for tk in survivors:
        df = hist[tk]
        fin = fund.get_financials(tk)
        ok, _ = passes_quality(fin, cfg)
        if not ok:
            quality_dropped += 1
            continue
        rec = fund.get_recommendation(tk)
        earn = earnings.get(tk)

        t_score, t_detail = trend_score(df, cfg)
        c_score, c_detail = catalyst_score(earn, rec, cfg)
        pb = evaluate_playbooks(df, cfg)
        g_score, g_detail = pb["trigger_score"], pb["trigger_detail"]
        # reversal entries stop tighter; continuation (or untriggered) uses the default
        stop_mult = (
            cfg["playbooks"]["reversal"]["atr_stop_mult"]
            if pb["playbook"] == "reversal"
            else None
        )
        risk = risk_eval(df, cfg, stop_mult=stop_mult)

        meta = meta_by.get(tk)
        # Prefer a curated sector (seed list); otherwise enrich from Finnhub's
        # profile so broad-universe names still group in the sector heatmap.
        sector = (meta.sector if meta and meta.sector != "—" else None) or fund.get_sector(tk) or "—"
        features.append(
            {
                "ticker": tk,
                "name": meta.name if meta else tk,
                "sector": sector,
                "price": round(float(df["close"].iloc[-1]), 2),
                "raw_momentum": raw_momentum(df["close"], bench_close, cfg),
                "high_prox01": high_proximity01(df["close"]),
                "trend_score": t_score,
                "trend_detail": t_detail,
                "catalyst_score": c_score,
                "catalyst_detail": c_detail,
                "trigger_score": g_score,
                "trigger_detail": g_detail,
                "trigger_passed": pb["trigger_passed"],
                "playbook": pb["playbook"],
                "playbooks": pb["playbooks"],
                "reversal_detail": pb["reversal_detail"],
                "continuation_score": pb["continuation_score"],
                "reversal_score": pb["reversal_score"],
                "reward_risk": risk["reward_risk"],
                "risk": risk,
                "rsi": round(float(rsi(df["close"], 14).iloc[-1]), 1),
                "change_1d": change_pct(df["close"], 1),
                "change_5d": change_pct(df["close"], 5),
                "change_21d": change_pct(df["close"], 21),
                "spark": spark(df, cfg),
            }
        )

    scored = score_all(features, cfg, regime)

    # market breadth over the scored universe
    n = len(features) or 1
    breadth = {
        "n": len(features),
        "pct_above_slow_ma": round(
            sum(1 for f in features if f["trend_detail"]["above_slow_ma"]) / n * 100, 1
        ),
        "pct_uptrend": round(
            sum(1 for f in features if f["trend_detail"]["fast_above_slow"]) / n * 100, 1
        ),
        "pct_advancing": round(
            sum(1 for f in features if f["change_1d"] > 0) / n * 100, 1
        ),
        "avg_rsi": round(sum(f["rsi"] for f in features) / n, 1),
    }

    universe_stats = {
        "considered": len(tickers) - 1,   # deep-dive candidates (excl. benchmark)
        "passed_liquidity": len(survivors),
        "passed_quality": len(features),
        "dropped": dropped,
        "quality_dropped": quality_dropped,
        "funnel": funnel_stats,           # None in legacy (seed/synthetic) mode
    }
    # enrich held positions with exit signals
    enriched_positions = []
    for p in positions or []:
        tk = p.get("ticker")
        df = hist.get(tk)
        item = dict(p)
        if df is not None and not df.empty:
            hw = p.get("high_watermark", p.get("entry_price", 0))
            item["exit"] = exit_signals(df, p["entry_price"], hw, cfg)
            m = meta_by.get(tk)
            item["name"] = m.name if m else tk
            item["sector"] = m.sector if m else "—"
        enriched_positions.append(item)

    provider_names = {"price": price.name, "fundamental": fund.name}
    return build_results(
        regime, scored, universe_stats, enriched_positions, provider_names, cfg, breadth
    )
