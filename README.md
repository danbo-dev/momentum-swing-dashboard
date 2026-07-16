# Momentum-Swing Dashboard

A personal stock-tracking dashboard for **multi-week to ~1-month swing trades**.
It screens the US market, ranks names by **momentum + catalysts behind a
quality/liquidity gate**, sizes by volatility, and surfaces the buy/sell story.

> Decision-support only — no orders are placed. Not investment advice.

## Architecture

```
Python engine (this repo /engine)                Next.js dashboard (/web)
  Polygon.io  -> prices + universe (EOD)            reads data/results.json
  Finnhub     -> earnings + analyst trends          (static / ISR, no live compute)
  gates -> factors -> score -> data/results.json         deployed on Vercel (free)
        run on a schedule by GitHub Actions,
        which commits results.json back to the repo -> Vercel auto-redeploys
```

See `../../.claude/plans/i-want-to-build-memoized-cascade.md` for the full plan
and the 2026 free-tier research behind these choices.

## Strategy (factor-modular)

- **Gates (hard filters):** liquidity (min price / dollar-volume) and a light
  quality screen. Junk and illiquid names never reach scoring.
- **Factors (weighted 0..1 sub-scores):**
  - *Momentum* (primary): blended 3/6/12-month **excess** return vs SPY, ranked
    cross-sectionally, plus 52-week-high proximity.
  - *Trend*: reward price above rising 50/200 MAs (buy strength).
  - *Catalyst*: post-earnings drift + improving analyst consensus; imminent
    earnings are flagged and damped, not rewarded.
  - *Trigger*: horizon-matched 20/50 EMA cross / pullback with an RSI band.
- **Risk:** ATR stop, R-multiple target, reward:risk filter, volatility sizing,
  and a market-regime throttle (SPY vs its 200-day).

All parameters live in `engine/config.yaml`. Promote quality/value from gate to
ranking factor by giving them a weight — the scorer renormalizes automatically.

## Run the engine

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# With no API keys it runs on SYNTHETIC data so you can see the whole pipeline:
python -m engine                 # -> data/results.json
python -m engine.backtest        # -> data/backtest.json

# For real data, copy .env.example -> .env.local and add free keys:
#   POLYGON_API_KEY   (https://polygon.io)
#   FINNHUB_API_KEY   (https://finnhub.io)
pytest engine/tests -q
```

Providers are chosen automatically: real keys → Polygon/Finnhub, otherwise
synthetic. On the Polygon free tier (5 calls/min) cap the universe with
`CONTEXT_UNIVERSE_LIMIT` while testing.
