"""Composite scoring.

Combines factor sub-scores (each 0..1) into a 0..100 composite using config
weights. Momentum is ranked CROSS-SECTIONALLY (percentile across the passing
universe) because relative strength is inherently relative; the other factors
are absolute. Buckets require confirmation (trigger + reward:risk) for the top tier.
"""
from __future__ import annotations

import pandas as pd


def score_all(features: list[dict], cfg: dict, regime: dict) -> list[dict]:
    if not features:
        return []
    fw = cfg["factors"]
    mom_hw = fw["momentum"]["high_52w_proximity_weight"]

    # cross-sectional percentile of blended-excess momentum
    raw = pd.Series({f["ticker"]: f["raw_momentum"] for f in features}, dtype="float64")
    pct = raw.rank(pct=True)  # NaNs stay NaN

    weights = {
        "momentum": fw["momentum"]["weight"],
        "trend": fw["trend"]["weight"],
        "catalyst": fw["catalyst"]["weight"],
        "trigger": fw["trigger"]["weight"],
    }

    throttle = (
        cfg["market_regime"]["throttle_when_risk_off"] and not regime["risk_on"]
    )

    out = []
    for f in features:
        mom_return_pct = float(pct.get(f["ticker"], 0.0) or 0.0)
        momentum_factor = (1 - mom_hw) * mom_return_pct + mom_hw * f["high_prox01"]

        subs = {
            "momentum": round(momentum_factor, 3),
            "trend": round(f["trend_score"], 3),
            "catalyst": round(f["catalyst_score"], 3),
            "trigger": round(f["trigger_score"], 3),
        }
        wsum = sum(weights.values())
        composite01 = sum(weights[k] * subs[k] for k in weights) / wsum
        composite = composite01 * 100.0

        regime_note = None
        if throttle:
            composite *= 0.85
            regime_note = "risk_off_throttle"

        # weighted point contributions for the "why" breakdown (sum ~ composite)
        contributions = {
            k: round(weights[k] * subs[k] / wsum * 100.0 * (0.85 if throttle else 1.0), 1)
            for k in weights
        }

        # Reversal-primary names rank on their own logic: recompute the composite
        # with reversal weights and the reversal trigger (not the momentum blend),
        # so a genuine early turn can qualify even with weak raw momentum.
        if f.get("playbook") == "reversal":
            rw = cfg["playbooks"]["reversal"]["weights"]
            subs = {**subs, "trigger": round(float(f.get("reversal_score", subs["trigger"])), 3)}
            rwsum = sum(rw.values())
            composite = sum(rw[k] * subs[k] for k in rw) / rwsum * 100.0
            if throttle:
                composite *= 0.85
            contributions = {
                k: round(rw[k] * subs[k] / rwsum * 100.0 * (0.85 if throttle else 1.0), 1)
                for k in rw
            }

        score = round(composite, 1)
        s = cfg["signals"]
        confirmed = f["trigger_passed"] and f["reward_risk"] >= cfg["risk"]["min_reward_risk"]
        if score >= s["strong_buy"] and confirmed:
            bucket = "strong_buy"
        elif score >= s["watch"]:
            bucket = "watch"
        else:
            bucket = "none"

        f2 = dict(f)
        f2.update(
            score=score,
            sub_scores=subs,
            contributions=contributions,
            momentum_percentile=round(mom_return_pct * 100, 1),
            bucket=bucket,
            confirmed=confirmed,
            regime_note=regime_note,
        )
        out.append(f2)

    out.sort(key=lambda x: x["score"], reverse=True)
    return out
