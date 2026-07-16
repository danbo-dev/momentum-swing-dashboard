"""Catalyst factor — earnings proximity/PEAD + analyst recommendation trend.

Over a ~1-month horizon, single-stock catalysts dominate. We reward positive
post-earnings drift and improving analyst consensus, and FLAG (not reward)
imminent earnings so the user never holds blindly into a print.
"""
from __future__ import annotations

from ..data.base import Earnings, Recommendation
from ..indicators import clamp01


def catalyst_score(earn: Earnings, rec: Recommendation, cfg: dict) -> tuple[float, dict]:
    c = cfg["factors"]["catalyst"]
    pead_w = c["pead_surprise_weight"]
    rec_w = c["rec_trend_weight"]

    # PEAD: map last EPS surprise (~ -0.2..+0.2) to 0..1 around 0.5
    surprise = earn.last_surprise_pct if earn and earn.last_surprise_pct is not None else 0.0
    pead01 = clamp01(0.5 + surprise * 2.5)

    # Recommendation trend: -1..+1 -> 0..1
    trend = rec.trend_score if rec and rec.trend_score is not None else 0.0
    rec01 = clamp01(0.5 + trend * 0.5)

    score = pead_w * pead01 + rec_w * rec01
    denom = pead_w + rec_w
    score = score / denom if denom else 0.0

    days_until = earn.days_until if earn else None
    earnings_soon = bool(days_until is not None and days_until <= c["earnings_soon_days"])
    if earnings_soon and not c["reward_pre_earnings"]:
        # imminent-earnings event risk over a swing hold — damp the score
        score *= 0.6

    detail = {
        "earnings_date": earn.next_date if earn else None,
        "days_to_earnings": days_until,
        "earnings_soon": earnings_soon,
        "last_surprise_pct": earn.last_surprise_pct if earn else None,
        "rec_trend": trend,
    }
    return float(clamp01(score)), detail
