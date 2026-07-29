# momentum-swing-dashboard — working notes

Multi-week swing screener. Python engine (`/engine`) → `web/public/data/results.json` → Next.js
dashboard (`/web`) on Vercel. GitHub Actions runs the engine once per trading session and commits
the JSON back, which triggers a redeploy. Repo is **public** and a real git clone.

> **This file is public.** No holdings, position sizes, P&L, or account balances. Engineering
> notes only — portfolio state lives in the private `strategy-gap-review` repo's `reports/`.

**`README.md` is the operating manual** — architecture, how to run things, the `HELD_TICKERS`
procedure, CI, stop simulation. This file holds what you can't infer from the code: invariants
that look like details but aren't, and the bugs that came from breaking them. Don't duplicate the
README here.

## Invariants — break these and the dashboard lies quietly

Each was a real production bug. None announced itself; all produced plausible-looking wrong
numbers.

**1. A scan is pinned to ONE trading session.** Resolved once in `run_scan` via
`session.py:resolve_session()` and threaded through the provider; cache keys name it
(`poly_hist_{tk}_{session}`). **Never put `date.today()` in a fetch path.** A cold run takes tens
of minutes, so a run that decides "today" per-fetch straddles the 16:00 ET close and caches some
tickers mid-session and some at the close under one key — the next run then reuses the blend.
Shipped prices matched no single session; 10 of 12 sampled names were off the real close, one by
3.3%. `results.json.as_of` states the session and coverage, and `__main__` refuses to publish
below `MIN_PCT_ON_SESSION` (90%).

**2. Held names are always quoted, even when they fail a gate.** `results.py` emits an
`unscored: true` market row for any held ticker missing from `scored`. Without it the UI has no
quote, `paper.ts:currentPrice` silently falls back to a frozen `lastMark`, and **the trailing stop
freezes with it** — a position showed a comfortable green cushion for days against a price three
sessions stale while it traded through its stop. The engine learns holdings from `$HELD_TICKERS`
(procedure in the README); a stale secret reintroduces exactly this.

**3. Trailing stops are resting orders, not close-based checks.** `paper.ts:stopFill()` triggers
on the session **low**; a bar that gapped below the level fills at the **open**, not the stop — a
resting order cannot fill above the market. It tests the **pre-ratchet** stop, because a daily bar
doesn't say whether the high preceded the low, and ratcheting first would invent a stop that never
rested. Close-based checks let price trade well through a stop and back: one position's low pierced
by 7 cents and closed $1.36 above, so nothing sold and the risk stayed on.

**4. Position sources are not uniform.** `positions.json` and book-export lots carry a cost basis;
a `$HELD_TICKERS` entry is only "always quote this name". `pipeline.enrich_positions()` skips the
exit grade when there's no entry price rather than faking one — subscripting `p["entry_price"]`
unconditionally killed a scheduled run 33 minutes in, on the one source CI actually uses.

## Reading the data honestly

- **Judge the strategy on `kind: "paper"` trades only.** The `real` lots are a migrated
  buy-and-hold seed (`migratedReal: true`) whose P&L swamps the swing results.
- **`trend_score` is not a ranking field** — it saturates at 1.0 for anything above both MAs.
  Rank on `score` (0–100).
- **Never compare a since-entry return to a fixed-window return.** The window starts before the
  position existed, so the shortfall is arithmetic, not skill. The gap review scores
  holding-period-matched excess vs SPY; this exact error produced a bogus "you're entering late"
  verdict.
- **Two conclusions were reversed by re-measurement** (2026-07-27): ATR-scaled trailing stops
  (replayed on real bars, a 2.5×ATR trail lost 3× more than the flat 10%) and late entries
  (entries sit ~0–3% above EMA20 at RSI 47–61 — not extended; `corr(RSI at entry, outcome)` is
  +0.44, the opposite sign to the thesis). Both looked obvious from summary statistics. Re-measure
  before acting on a single-sample read.

## State

- **2026-07-29** — Trailing stops fire intraday with gap-aware fills; `results.py` exposes the
  session `open`. One position was retroactively closed at its stop to correct history the
  close-based logic had missed. Positions moved above Opportunities and every section collapses
  (`Collapsible.tsx`, state persisted per section). Opportunities carry a `held` badge and an
  "Add to X" button — the engine force-*includes* held names so they keep ranking, and two
  accidental double-buys had already happened before it shipped.
- **2026-07-28** — Per-endpoint Finnhub TTLs. Fundamentals were ~95% of a cold scan
  (`fundamentals+features` 1311s + `earnings` 518s of 1932s) because one global 20h TTL refetched
  everything daily, including sectors that never change. `results.json.timings_sec` records
  wall-clock per stage — **read it before optimising anything**; the prime suspect at the time
  (`grouped_bars`, 90 whole-market responses) turned out to be 4.5s.
- **2026-07-27** — Sessions pinned; midday run dropped; single post-close schedule.

## Gotchas

- **`~/Documents` is iCloud-synced**, which litters `node_modules` with `"name 2"` conflict copies.
  TypeScript treats every directory in `@types/` as an implicit type library, so a stray
  `@types/node 2` fails the build with `Cannot find type definition file for 'node 2'`. Fix:
  `rm -rf node_modules && npm ci`. CI never sees this — it installs clean.
- **The book is in browser localStorage (`msd_paper_v1`)**, not on disk.
  `web/public/data/positions.json` and `results.json.positions` are empty seeds. Editing an
  exported file changes nothing until it is **imported back through the dashboard**.
- **Polygon is Stocks Starter — unlimited calls**, so it is not the bottleneck and there is no 429
  backoff. Finnhub's 60/min free tier is the real limit; the limiter sits at 55 because sitting
  exactly on 60 trips 429s and the backoff costs more than the spacing saves.
- **`python -m engine` on synthetic data does not finish quickly** — it reaches for network. Test
  engine changes with targeted unit calls, not a full scan.
- **Toolchain:** Homebrew at `/opt/homebrew`, Node 26 / npm 11; engine deps in the repo `.venv`.
  Non-login shells may lack brew on PATH — prefix with
  `eval "$(/opt/homebrew/bin/brew shellenv zsh)"`.

## Backlog

- **Verify the Finnhub TTL saving** on the next cold run via `timings_sec`; projected ~27 min →
  ~4.5 min on per-ticker fundamentals.
- **Instrument `engine.backtest`** — ~35 min, uninstrumented, roughly doubles the job's wall clock.
- **Watch the exit rate.** Intraday stops fire more often than close-based ones. That's intended,
  but it is a real strategy change and should show up as more closed trades and shorter holds in
  the next gap review. Confirm it's an improvement rather than assuming.
- **Surface `acknowledgeBreach`** — the helper exists in `paper.ts` but nothing calls it, so a
  latched breach flag clears only by selling.
- **Automate `HELD_TICKERS`** so holdings reach CI without a manual secret update.
- **Rejected — do not retry without new evidence:** ATR-scaled trailing stops; entry-timing
  changes. Both investigated 2026-07-27, evidence under "Reading the data honestly".
