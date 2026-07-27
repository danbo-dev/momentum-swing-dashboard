# momentum-swing-dashboard

Multi-week swing screener. Python engine (`/engine`) → `web/public/data/results.json` → Next.js
dashboard (`/web`) on Vercel. GitHub Actions runs the engine ~twice daily and commits the JSON
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

## Gotchas

- **The book is in browser localStorage (`msd_paper_v1`), not on disk.** Both
  `web/public/data/positions.json` and `results.json.positions` are empty seeds. Export via the
  dashboard's **Export / More ▾**; the download is named `positions.json` — rename it to
  **`book_export.json`** in the repo root. It is gitignored (it holds P&L), so **CI cannot see it**;
  that is what `HELD_TICKERS` exists for.
- **No node/npm on this machine.** Engine tests run (`python -m pytest engine/tests`, needs the
  `.venv`); nothing in `web/` can be typechecked locally. The `web` workflow runs
  `npm ci && npm run build` on every `web/**` push so TypeScript is still verified — check the
  commit status rather than building locally.
- `python -m engine` on synthetic data does **not** finish quickly — it reaches for network. Test
  engine changes with targeted unit calls, not a full scan.
- **Judge strategy performance on `kind: "paper"` trades only.** The `real` lots are a migrated
  buy-and-hold seed (`migratedReal: true`) whose P&L swamps the swing results.
- The paper account's `startingCapital` does not match `config.yaml`'s `capital`, so every
  "% of capital" the dashboard shows is off by that ratio. Sizing itself follows
  `max_budget_per_trade` and is fine.
- `trend_score` saturates at 1.0 for any name above both MAs — never rank on it; use `score`.

## Deferred backlog

- **ATR-scale the trailing stop.** A flat `defaultTrailPct` stopped most paper trades out within
  ~2 days, one at breakeven — noise, not thesis. `risk_eval` already computes ATR.
- **Reconcile `startingCapital`** with `config.yaml`.
- **Surface `acknowledgeBreach` in the UI** — the helper exists in `paper.ts` but nothing calls it,
  so a latched breach flag currently clears only by selling.
- **Automate `HELD_TICKERS`** (see above) so holdings reach CI without a manual secret update.
- **Entry timing** — momentum ranking buys after the move; the `reversal_lane` is the counterweight.
  Track since-entry vs window return in the weekly gap review.
