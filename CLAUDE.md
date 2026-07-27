# momentum-swing-dashboard

Multi-week swing screener. Python engine (`/engine`) → `web/public/data/results.json` → Next.js
dashboard (`/web`) on Vercel. GitHub Actions runs the engine once per session and commits the JSON
back, which triggers a redeploy. Repo is **public** and a real git clone — edits here can be pushed.

> **This file is public.** Keep portfolio specifics out of it — no holdings, position sizes, P&L,
> or account capital. Engineering notes only. Performance state lives in the private
> `strategy-gap-review` repo's `reports/`.

## The bug behind the held-quote fix (read before touching marks)

A held position that drops out of the scan **silently freezes at a stale price, and its trailing
stop freezes with it** — the dashboard kept showing a comfortable green cushion computed from a
days-old price while the name was actually trading through its stop.

Chain of causation:
1. `market` in `results.json` was built only from `scored` names, so a holding that failed a gate
   had no quote at all.
2. `paper.ts:currentPrice` falls back to `lot.lastMark` when there is no quote — silently.
3. `applyMarks` skipped lots with no quote, so the stop never re-evaluated.
4. `pipeline.py` *does* force-include held tickers (`held`), but `held` came from `positions.json`,
   which is **empty** — the real book lives in browser localStorage.

Fixes: `results.py` emits a quote for every held ticker even when unscored (`unscored: true`) and
adds `low`/`high`/`asof` to every market row; `paper.ts` latches a `breachedAt` flag the first time
a price *or session low* trades through the stop and records `lastMarkDate`;
`__main__.py:_load_positions` falls back to `book_export.json` then `$HELD_TICKERS`.

## HELD_TICKERS — needs maintenance

`HELD_TICKERS` is a **repository secret** (comma-separated, e.g. `"AAA,BBB,CCC"`) that tells the
scheduled scan which names to force-include and always quote. It is a secret rather than a variable
because this repo is public and the value is the owner's open positions.

**It does not update itself.** The engine cannot see the book — localStorage is unreachable from CI
— so a stale secret silently reintroduces the exact bug above: a newly-bought name that isn't in
the screen never gets quoted, and a sold name wastes a quote.

**Update it whenever the book changes** (buy, sell, or trim):

```bash
gh secret set HELD_TICKERS --repo <owner>/momentum-swing-dashboard --body "AAA,BBB,CCC"
```

Or: repo → Settings → Secrets and variables → Actions → `HELD_TICKERS` → update. Values are
write-only; re-set to change. Derive the list from a fresh `book_export.json`:

```bash
python3 -c "import json;print(','.join(l['ticker'] for l in json.load(open('book_export.json'))['lots']))"
```

Trimming an over-held name or rotating into a new one **both** require this — the sell alone
doesn't remove it, and the buy alone doesn't add it. Treat it as the last step of any trade, and
re-check it during the weekly gap review (that's when a fresh export exists anyway).

Longer-term fix on the backlog: have the dashboard write the ticker list somewhere CI can read, so
the secret stops being a manual step.

## Sessions — the load-bearing invariant

A scan is **not** a point in time: a cold run takes ~2h on Polygon's free tier. Every fetch is
therefore pinned to one trading session, resolved ONCE in `run_scan` via
`engine/session.py:resolve_session()` and threaded through the provider. Cache keys name that
session (`poly_hist_{tk}_{session}`), so run duration, cron lag, queueing and DST cannot change
what a run means.

**Never reintroduce `date.today()` into a fetch path.** That was the bug: the midday scan
straddled the 16:00 ET close, cached some tickers mid-session and some at the close under one
calendar-date key, and the post-close run reused the blend for up to `cache_ttl_hours: 20`.
Shipped prices matched no single session — 10 of 12 sampled names were off the real close, by up
to 3.3%. `results.json.as_of` now states the session and what share of names actually carry it;
`__main__` refuses to publish below `MIN_PCT_ON_SESSION` (90%).

Use `SESSION_DATE=YYYY-MM-DD` to pin a run for backfills or reproducible tests.

## Schedule

**One scan per session**, `cron: "15 21 * * 1-5"` — post-close in both EDT (17:15 ET) and EST
(16:15 ET), so it survives the DST change rather than relying on ~60 min of runner lag. Cold run
~2h, so data lands ~20:30 ET for a next-morning review.

There is deliberately **no midday run**. It could not do what its name implied — `get_recent_bars`
reads only completed sessions, so a midday scan reproduced the previous evening's frame — and it
was the thing corrupting the cache. If you ever want an intraday read, it needs a different data
path, not a differently-timed run.

## Gotchas

- **The book is in browser localStorage (`msd_paper_v1`), not on disk.** Both
  `web/public/data/positions.json` and `results.json.positions` are empty seeds. Export via the
  dashboard's **Export / More ▾**; the download is named `positions.json` — rename it to
  **`book_export.json`** in the repo root. It is gitignored (it holds P&L), so **CI cannot see it**;
  that is what `HELD_TICKERS` exists for.
- **Toolchain (as of 2026-07-26):** Homebrew at `/opt/homebrew`, Node 26 / npm 11 via
  `brew install node`. Python deps for the engine live in the repo's `.venv`.
  - engine: `. .venv/bin/activate && python -m pytest engine/tests -q`
  - web: `cd web && npm ci && npm run build` (`next build` typechecks, so this is the typecheck)
  - The `web` workflow runs the same build on every `web/**` push, so CI covers it either way.
  - Non-login shells may not have brew on PATH; prefix with
    `eval "$(/opt/homebrew/bin/brew shellenv zsh)"` if `node` isn't found.
- `python -m engine` on synthetic data does **not** finish quickly — it reaches for network. Test
  engine changes with targeted unit calls, not a full scan.
- **`~/Documents` is iCloud-synced, which litters `node_modules` with `"name 2"` conflict copies.**
  TypeScript treats every directory in `@types/` as an implicit type library, so a stray
  `@types/node 2` fails the build with `Cannot find type definition file for 'node 2'`. Fix:
  `rm -rf node_modules && npm ci`. CI never sees this — it installs clean.
- **`data.polygon.rate_limit_per_min` is 100, but the free tier is 5/min** (README says so, and a
  ~500-ticker run taking ~2h matches ~5/min). The limiter therefore doesn't throttle; Polygon 429s
  and `_http.py` backs off 5/10/20/40s, and a ticker can be dropped after 4 failures. Setting it to
  5 would likely be faster *and* lossless — unverified against the actual plan.
- **Judge strategy performance on `kind: "paper"` trades only.** The `real` lots are a migrated
  buy-and-hold seed (`migratedReal: true`) whose P&L swamps the swing results.
- `trend_score` saturates at 1.0 for any name above both MAs — never rank on it; use `score`.

## Deferred backlog

- **Reconsider the trailing stop only with more data.** ATR-scaling was investigated 2026-07-27 and
  **rejected**: replayed on real bars a 2.5xATR trail lost $246 vs the flat 10%'s $80 across the
  four closed paper trades — all four kept falling after the stop. Revisit after ~20 more trades.
- **Confirm `data.polygon.rate_limit_per_min`** against the actual plan (see gotcha).
- **Surface `acknowledgeBreach` in the UI** — the helper exists in `paper.ts` but nothing calls it,
  so a latched breach flag currently clears only by selling.
- **Automate `HELD_TICKERS`** (see above) so holdings reach CI without a manual secret update.
- **Entry timing** — investigated 2026-07-27 and **not established**: entries sit ~0-3% above EMA20
  at RSI 47-61 (not extended), and corr(RSI at entry, outcome) is +0.44. The earlier "buying late"
  read came from comparing a 21-day window to a ~12-day hold. The gap review now tracks
  holding-period-matched excess vs SPY plus `pre_entry_run_pct`; revisit with ~20 more trades.
