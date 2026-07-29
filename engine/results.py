"""Assemble the results.json payload — the contract between engine and web UI."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from .indicators import atr, ema, rsi
from .session import session_is_current

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


def _bar_context(df: pd.DataFrame | None) -> dict:
    """Session open/low/high + the bar's date. A trailing stop is a resting order, so
    the UI needs the intraday path to simulate it: `low` says whether the stop was hit,
    and `open` gives the realistic fill when the price gapped straight through it."""
    if df is None or df.empty:
        return {}
    return {
        "open": round(float(df["open"].iloc[-1]), 2),
        "low": round(float(df["low"].iloc[-1]), 2),
        "high": round(float(df["high"].iloc[-1]), 2),
        "asof": df.index[-1].strftime("%Y-%m-%d"),
    }


def _unscored_quote(df: pd.DataFrame, cfg: dict) -> dict:
    """Minimal market entry for a HELD name that never reached `scored` (failed the
    liquidity or quality gate, or fell out of the funnel bucket).

    Without this the UI has no quote for the position and silently falls back to a
    frozen `lastMark` — which also freezes its trailing stop. A name you own dropping
    out of the screen is exactly when you most need it marked, so quote it anyway and
    tag it `unscored` so the UI can say why it isn't ranked.
    """
    close = df["close"]
    t = cfg["factors"]["trigger"]
    q = {
        "price": round(float(close.iloc[-1]), 2),
        "ema_fast": round(float(ema(close, t["ema_fast"]).iloc[-1]), 2),
        "ema_slow": round(float(ema(close, t["ema_slow"]).iloc[-1]), 2),
        "atr": round(float(atr(df["high"], df["low"], close, cfg["risk"]["atr_period"]).iloc[-1]), 3),
        "rsi": round(float(rsi(close, 14).iloc[-1]), 1),
        "unscored": True,
    }
    q.update(_bar_context(df))
    return q


def build_results(
    regime: dict,
    scored: list[dict],
    universe_stats: dict,
    positions: list[dict],
    provider_names: dict,
    cfg: dict,
    breadth: dict | None = None,
    hist: dict | None = None,
    held: set | None = None,
    session=None,
    timings: dict | None = None,
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
    hist = hist or {}
    market = {}
    for x in scored:
        if not (x.get("spark", {}).get("ema_fast") and x.get("risk")):
            continue
        q = {
            "price": x["price"],
            "ema_fast": round(float(x["spark"]["ema_fast"][-1]), 2),
            "ema_slow": round(float(x["spark"]["ema_slow"][-1]), 2),
            "atr": x["risk"]["atr"],
            "rsi": x["rsi"],
        }
        q.update(_bar_context(hist.get(x["ticker"])))
        market[x["ticker"]] = q

    # Held names that failed a gate are missing from `scored` — quote them anyway.
    for tk in sorted(held or set()):
        if tk in market:
            continue
        df = hist.get(tk)
        if df is None or df.empty:
            continue
        try:
            market[tk] = _unscored_quote(df, cfg)
        except Exception:  # never let one holding break the whole payload
            continue
    # Self-describing output: say which session these prices are FOR, and how well the
    # data actually matches it. `generated_at` alone hid a two-hour price blend for
    # weeks — a payload that states its own as-of makes that failure loud instead.
    bar_dates = [q["asof"] for q in market.values() if q.get("asof")]
    on_session = sum(1 for d in bar_dates if session and d == session.isoformat())
    session_block = {
        "session": session.isoformat() if session else None,
        "names_on_session": on_session,
        "names_quoted": len(bar_dates),
        "pct_on_session": round(on_session / len(bar_dates) * 100, 1) if bar_dates else None,
        "current": session_is_current(session) if session else None,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": session_block,
        "timings_sec": timings or {},
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
