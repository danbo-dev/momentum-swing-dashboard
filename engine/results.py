"""Assemble the results.json payload — the contract between engine and web UI."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from .indicators import ema

SCHEMA_VERSION = 2


def spark(df: pd.DataFrame, cfg: dict, n: int = 60) -> dict:
    """Compact series for a row sparkline / mini chart (last n bars)."""
    close = df["close"]
    fast = ema(close, cfg["factors"]["trigger"]["ema_fast"])
    slow = ema(close, cfg["factors"]["trigger"]["ema_slow"])
    tail = df.iloc[-n:]
    return {
        "dates": [d.strftime("%Y-%m-%d") for d in tail.index],
        "close": [round(float(x), 2) for x in close.iloc[-n:]],
        "ema_fast": [round(float(x), 2) for x in fast.iloc[-n:]],
        "ema_slow": [round(float(x), 2) for x in slow.iloc[-n:]],
        "volume": [int(x) for x in tail["volume"]],
    }


def change_pct(close: pd.Series, bars: int) -> float:
    if len(close) <= bars:
        return 0.0
    return round(float(close.iloc[-1] / close.iloc[-1 - bars] - 1) * 100, 2)


def build_results(
    regime: dict,
    scored: list[dict],
    universe_stats: dict,
    positions: list[dict],
    provider_names: dict,
    cfg: dict,
    breadth: dict | None = None,
) -> dict:
    s = cfg["signals"]
    # top_n by score, PLUS every qualifying reversal setup (they rank lower on the
    # momentum-composite sort and would otherwise be crowded out of the cap).
    ranked = [x for x in scored if x["bucket"] != "none"]
    opportunities = ranked[: s["top_n"]]
    seen = {x["ticker"] for x in opportunities}
    for x in ranked:
        if x.get("playbook") == "reversal" and x["ticker"] not in seen:
            opportunities.append(x)
            seen.add(x["ticker"])
    # Last-value indicators for every scored name (no extra computation/API calls)
    # so the web UI can grade exits for any scanned holding, not just the top_n
    # opportunities. Mirrors the fields web/lib/exitSignals.ts::MarketData expects.
    market = {
        x["ticker"]: {
            "price": x["price"],
            "ema_fast": round(float(x["spark"]["ema_fast"][-1]), 2),
            "ema_slow": round(float(x["spark"]["ema_slow"][-1]), 2),
            "atr": x["risk"]["atr"],
            "rsi": x["rsi"],
        }
        for x in scored
        if x.get("spark", {}).get("ema_fast") and x.get("risk")
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "providers": provider_names,
        "strategy": {
            "name": "Momentum + catalysts (quality-gated)",
            "horizon": "multi-week to ~1 month",
            "factor_weights": {k: v["weight"] for k, v in cfg["factors"].items()},
        },
        "market_regime": regime,
        "breadth": breadth or {},
        "universe": universe_stats,
        "buckets": {
            "strong_buy": sum(1 for x in scored if x["bucket"] == "strong_buy"),
            "watch": sum(1 for x in scored if x["bucket"] == "watch"),
        },
        "opportunities": opportunities,
        "market": market,
        "snapshot": [
            {
                "ticker": x["ticker"],
                "sector": x.get("sector", "—"),
                "score": x["score"],
                "change_21d": x["change_21d"],
                "change_5d": x["change_5d"],
                "bucket": x["bucket"],
                "playbook": x.get("playbook"),
            }
            for x in scored
        ],
        "positions": positions,
    }
