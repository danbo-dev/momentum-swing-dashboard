# Exit signals everywhere + broad-universe funnel + two entry playbooks

## Context

Reviewing the unified Positions work, the user raised that **exit signals are critical for
real money**, and that the current design has three gaps:

1. **Exit signals don't reach every holding.** The engine computes EMA/ATR/RSI for every
   scanned name but only *publishes* them for the ~24 opportunities, so a real holding outside
   that set shows the trailing stop only. (Root cause of the user's concern.)
2. **The universe is too narrow.** The base is a hand-picked **79-name seed**
   (`engine/data/seed_universe.py`), not the broad market — so opportunities are missed. Funnel
   today: 79 → liquidity → 73 → quality → 61 scored → top 24 shown.
3. **The thesis enters too late.** Current strategy is trend-*continuation* (buy above rising
   50/200-MA, 20/50 EMA-cross trigger) — it misses the early upswing. User wants to also catch
   **early reversals** (5/9 cross, RSI lifting off oversold, reclaiming MAs from below).

**Cadence (confirmed, for the UI/docs):** engine runs twice/weekday (~1pm ET midday, ~40min
after the 4pm close) + manual trigger; Polygon free data is **daily (EOD) bars**, not intraday.

**Confirmed design decisions:**
- Broad base (whole market) → **cheap whole-market screen** (Polygon grouped-daily, ~1 call/day
  for all prices) → **filters determine the daily bucket** (numeric cap is only a rate-limit
  backstop that *tightens thresholds*, never an arbitrary top-N slice) → **deep-dive** on the
  bucket (per-ticker history + fundamentals).
- Stage-2 ranking: **liquidity floor, then momentum rank.**
- **Two entry playbooks, tagged**: *Continuation* (established uptrends, pullback entries) and
  *Early reversal* (fast 5/9 cross, oversold-turning, MA reclaim from below), each with its own
  stop logic; every opportunity tagged by playbook.
- Price band starting default $5–$500 (configurable; note a hard $500 cap drops some large-caps).

Constraint: Polygon free tier 5 calls/min; `engine/.cache/` is gitignored with no CI cache, so
runs start cold today. Deployed static on Vercel; engine runs in GitHub Actions.

---

## Phase 1 — Exit signals for every scanned name (ship first; small, low-risk)

Publish the indicators the engine already computes so any scanned holding gets the full
4-signal exit grade the old Tracked Positions panel had.

- **`engine/results.py`** `build_results`: add
  `market: { TICKER: {price, ema_fast, ema_slow, atr, rsi} }` for every `x in scored`, pulling
  `x["spark"]["ema_fast"][-1]`, `["ema_slow"][-1]`, `x["risk"]["atr"]`, `x["rsi"]`, `x["price"]`.
  No new computation or API calls.
- **`web/lib/types.ts`**: add optional `market?: Record<string, MarketRow>` to `Results`.
- **`web/app/page.tsx`**: merge `r.market` into the `quotes` map (ema/atr/rsi/price) so
  `PortfolioPanel` → `computeExitSignals` (already built in `web/lib/exitSignals.ts`) fires for
  all scanned names, not just opportunities.
- **`web/components/PortfolioPanel.tsx`**: refine the "limited signals" note to say full signals
  cover any scanned name; a holding outside the scan stays trailing-stop-only until Phase 2.

After Phase 1, coverage = all ~61 scored names (vs 24). Broad coverage comes in Phase 2.

---

## Phase 2 — Broad-universe funnel (the big build)

Make broad scanning feasible on the free tier by screening cheap and deep-diving narrow.

**New data path — `engine/data/polygon.py`:**
- Implement `get_grouped_daily(date)` → Polygon `/v2/aggs/grouped/locale/us/market/stocks/{date}`
  (whole market OHLCV in 1 call). Wire the existing unused `grouped_daily` flag. Fetch the last
  ~25 trading days grouped (≈25 cached calls) to build a whole-market recent-bars frame for the
  cheap screen. Keep per-ticker `get_history` for the **bucket only** (full 400-day history).
- `get_universe(use_seed_universe=false)`: already paginates `reference/tickers`; keep for the
  base list + type/exchange/name-exclusion filters.

**CI — `.github/workflows/engine.yml`:** add `actions/cache` for `engine/.cache/` keyed by
run-date so full-history frames persist; steady-state runs fetch only new days + new-to-bucket
tickers. (Cold first run is slow, one-time.)

**Pipeline — `engine/pipeline.py` (staged funnel):**
- *Stage 0* base list (reference/tickers, filtered).
- *Stage 1* cheap whole-market screen from grouped-daily: latest close + 20-day median dollar
  volume → price band + liquidity floor + `min_history_days`. → ~800–1500 names.
- *Stage 2* **filter cascade → bucket**: liquidity floor, then momentum rank (blended excess
  return, computed from the grouped bars we already have). Whatever passes = the bucket; a
  `funnel.max_bucket` backstop *raises thresholds* if exceeded (logged), never chops arbitrarily.
- *Stage 3* deep-dive on the bucket (existing per-ticker `get_history` + Finnhub fundamentals +
  trend/catalyst/trigger/risk/score) — unchanged logic, new (bucket) input.

**Config — `engine/config.yaml`:** new `funnel` section (price_band, min_dollar_volume,
momentum_rank_keep, max_bucket) and flip `use_seed_universe: false`. Keep the seed as a
fallback/offline default.

**Frontend:** surface funnel stats (base → screened → bucket → scored) in the universe panel so
coverage is transparent.

---

## Phase 3 — Two entry playbooks (continuation + early reversal)

**`engine/strategy/trigger.py` (or a new `playbooks.py`):** evaluate two setups per name and tag:
- *Continuation*: existing 20/50 EMA-cross + above rising 50/200-MA + pullback/RSI band.
- *Early reversal*: **5/9 (or 9/21) EMA cross up** + RSI turning up from oversold (e.g. crossing
  back above ~35) + price reclaiming the 50-MA (and flag names reclaiming the 200-MA from below).
  Tighter ATR stop (reversal risk) via a per-playbook stop mult in `engine/strategy/risk.py`.
- Emit `playbook: "continuation" | "reversal"` (a name can qualify for both) + per-playbook
  score so each list ranks on its own logic.

**Publish + UI:** add `playbook` to opportunities (`results.py`, `web/lib/types.ts`); the
Opportunity table shows a playbook badge and a filter (Continuation / Reversal / All);
`MetricsGlossary` documents both playbooks and their stop logic. Backtest split by playbook is a
later follow-up.

*Framing:* these are configurable screening rules; tradeoffs stated factually (earlier entry =
more false signals), no return/profit claims.

---

## Sequencing & scope

Build **Phase 1 now** — it directly fixes the real-money exit-signal gap, is low-risk, and reuses
the exit-signal engine already built. Then **check in** before Phase 2 (engine rewrite + CI
caching + rate-limit tuning) and Phase 3 (new strategy logic + backtest implications), refining
thresholds/playbook definitions as we go. Each phase is independently shippable.

## Verification

- **Phase 1:** `cd web && rm -rf .next && npm run dev`; a holding on a scanned name (e.g. an
  opportunity ticker) now shows all 4 exit signals + urgency; assert `computeExitSignals` output
  matches the engine's `exit_signals` on a shared example; `npm run build` clean. Re-run engine
  (`python -m engine`) and confirm `results.json` has a populated `market` map.
- **Phase 2:** run `python -m engine` with `use_seed_universe:false`; assert funnel cardinalities
  logged (base → screened → bucket), bucket ≤ backstop, call count within budget; `pytest engine/tests`.
- **Phase 3:** unit-test both trigger evaluators on synthetic uptrend vs reversal fixtures;
  confirm opportunities carry `playbook`; UI filter works.
- Never run `npm run build` against a live dev server (corrupts `.next`).
