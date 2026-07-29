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
synthetic. This project runs on Polygon **Stocks Starter** (unlimited API calls,
15-min delayed, 5y history), so `data.polygon.rate_limit_per_min` is set high
enough to effectively disable spacing. Finnhub's free tier (60/min) is the real
limiter. If you run on Polygon's free tier instead (5 calls/min), lower that
value and cap the universe with `CONTEXT_UNIVERSE_LIMIT`.

## Positions & trailing stops

Positions are logged in the browser (localStorage `msd_paper_v1`) — the engine places no
orders and never sees your book. Export/import via **Export / More ▾**; the download is
named `positions.json`, rename it to `book_export.json` in the repo root if you want the
engine or the gap-review skill to read it. **Editing an exported file changes nothing
until you import it back.**

Trailing stops are simulated as **resting orders**, not close-based checks:

| Bar | Result |
|---|---|
| Session low pierces the stop | fills **at the stop** |
| Bar gapped below the stop (open ≤ stop) | fills **at the open** — a resting order can't fill above the market |
| Stop untouched | no fill |

Two details that matter:

- The level tested is the **pre-ratchet** stop — the one actually resting during that bar.
  A daily bar doesn't reveal whether the high came before the low, so ratcheting the
  high-water mark first would invent a stop that never existed.
- Marks arrive on the engine's daily cadence, so a stop is detected on the **first scan
  after** the session it was hit — not intraday. `stopMode: "alert"` flags instead of
  selling; `"auto"` closes the lot.

A latched **breach flag** records the first time price traded through the stop, and is not
cleared by a recovery — so a dip on a day you didn't check still surfaces. In alert mode an
intraday-only breach shows amber ("dipped under stop"); a close through the level shows red.

## Held positions (`HELD_TICKERS`) — keep this current

The scan force-includes held tickers and **always quotes them, even if they fail a
gate or fall out of the screen**. Without that, a holding the screen drops has no
price in `results.json`, the dashboard silently falls back to the last mark it saw,
and the trailing stop freezes along with it — showing a healthy cushion against a
stale price.

Holdings live in browser localStorage, which CI cannot read, so the scheduled run
learns them from a `HELD_TICKERS` **repository secret** (a secret, not a variable —
in a public repo the value is your positions):

```bash
gh secret set HELD_TICKERS --body "AAA,BBB,CCC"
# or: Settings -> Secrets and variables -> Actions
```

**This does not update itself.** Re-set it whenever the book changes — after a buy,
a sell, or a trim. A sold name left in the list only wastes a quote, but a *new*
holding left out reintroduces the stale-price bug. Locally, `python -m engine` reads
`data/positions.json`, then a `book_export.json` in the repo root (gitignored), then
`$HELD_TICKERS` — first non-empty wins.

## Schedule & CI

- **`engine`** — one scan per trading session, `cron: "15 21 * * 1-5"`. That is post-close in
  both EDT (17:15 ET) and EST (16:15 ET), so it survives the DST change rather than relying on
  runner lag. GitHub's scheduler runs ~60 min late, so expect a ~22:15 UTC start; data lands
  early evening ET, ready for a next-morning review. There is deliberately **no midday run** —
  the funnel reads only completed sessions, so a midday scan reproduced the previous evening's
  frame while corrupting the price cache.
- **`web`** — `npm ci && npm run build` on every `web/**` push. `next build` typechecks, so this
  verifies TypeScript without a local Node install.

Every run stamps `results.json` with `as_of` (which session the prices are for, and what share
of names actually carry a bar from it) and `timings_sec` (wall clock per stage). The engine
**refuses to publish** if under 90% of quoted names match the claimed session — prices that
match no single session shipped undetected for weeks before that check existed.

## Troubleshooting

| Symptom | Cause |
|---|---|
| A holding shows a stale price and a frozen stop | It fell out of the scan and isn't in `HELD_TICKERS` |
| Header says `closes <older date>` in warning colour | A newer session has completed; the scan hasn't run or failed |
| `Cannot find type definition file for 'node 2'` | iCloud conflict copies in `node_modules` — `rm -rf node_modules && npm ci` |
| Engine run fails the publish gate | Prices don't match the claimed session; check `as_of` in the log |
