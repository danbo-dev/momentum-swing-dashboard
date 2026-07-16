from engine.config import load_config
from engine.pipeline import run_scan
from engine.strategy.scoring import score_all


def _feature(ticker, raw_mom, trend, catalyst, trigger, passed, rr, high=0.9):
    return {
        "ticker": ticker,
        "raw_momentum": raw_mom,
        "high_prox01": high,
        "trend_score": trend,
        "catalyst_score": catalyst,
        "trigger_score": trigger,
        "trigger_passed": passed,
        "reward_risk": rr,
    }


def test_scoring_orders_and_breaks_down():
    cfg = load_config()
    regime = {"risk_on": True}  # no throttle
    feats = [
        _feature("STRONG", 0.9, 1.0, 0.8, 1.0, True, 3.0),
        _feature("WEAK", -0.5, 0.1, 0.2, 0.0, False, 1.0, high=0.1),
    ]
    scored = score_all(feats, cfg, regime)
    assert scored[0]["ticker"] == "STRONG"
    assert scored[0]["score"] > scored[1]["score"]
    # contributions sum ~ composite score
    strong = scored[0]
    assert abs(sum(strong["contributions"].values()) - strong["score"]) < 0.5


def test_risk_off_throttle_lowers_score():
    cfg = load_config()
    feats = [_feature("X", 0.9, 1.0, 0.8, 1.0, True, 3.0)]
    on = score_all(feats, cfg, {"risk_on": True})[0]["score"]
    off = score_all(feats, cfg, {"risk_on": False})[0]["score"]
    assert off < on


def test_strong_buy_requires_confirmation():
    cfg = load_config()
    # high sub-scores but trigger not passed / poor R:R => cannot be strong_buy
    feats = [_feature("NOCONF", 0.99, 1.0, 1.0, 1.0, False, 1.0)]
    s = score_all(feats, cfg, {"risk_on": True})[0]
    assert s["bucket"] != "strong_buy"


def test_pipeline_smoke_synthetic(monkeypatch):
    # Force the synthetic providers even when a local .env.local supplies real API
    # keys, so the smoke test never fires live calls (a broad-funnel run would).
    for k in ("POLYGON_API_KEY", "TIINGO_API_KEY", "FINNHUB_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    r = run_scan()
    assert r["schema_version"] >= 1
    assert r["providers"]["price"] == "synthetic"
    assert "opportunities" in r
    # gates drop the junk names
    tickers = {o["ticker"] for o in r["opportunities"]}
    assert "PENNY" not in tickers  # price < $5
    for o in r["opportunities"]:
        assert set(o["sub_scores"]) == {"momentum", "trend", "catalyst", "trigger"}
        assert "reward_risk" in o["risk"]
