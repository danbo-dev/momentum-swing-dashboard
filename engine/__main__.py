"""Entry point: run the scan and write data/results.json.

Usage:
    python -m engine              # run scan -> data/results.json
    python -m engine --out path   # custom output path
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .pipeline import run_scan

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "web" / "public" / "data"
DEFAULT_OUT = DATA_DIR / "results.json"


def _load_positions() -> list[dict]:
    """Held positions, so the scan force-includes them and always quotes them.

    The real book lives in the browser (localStorage `msd_paper_v1`), which CI cannot
    read — an empty list here is why a holding that drops out of the screen stops being
    priced in the dashboard. Three sources, first non-empty wins:

      1. data/positions.json           — committed seed
      2. book_export.json              — local dashboard export (gitignored: has P&L)
      3. $HELD_TICKERS                 — "EZPW,KOD,NVCR"; set as a CI secret to keep the
                                         holdings list private in a public repo
    """
    p = DATA_DIR / "positions.json"
    if p.exists():
        try:
            got = json.loads(p.read_text()).get("positions", [])
            if got:
                return got
        except Exception:
            pass

    export = REPO_ROOT / "book_export.json"
    if export.exists():
        try:
            lots = json.loads(export.read_text()).get("lots", [])
            got = [
                {"ticker": l["ticker"], "shares": l.get("shares"),
                 "entry_price": l.get("entryPrice"), "entry_date": l.get("entryDate")}
                for l in lots if l.get("ticker")
            ]
            if got:
                return got
        except Exception:
            pass

    env = os.getenv("HELD_TICKERS", "")
    return [{"ticker": t.strip().upper()} for t in env.split(",") if t.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="engine")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args(argv)

    results = run_scan(positions=_load_positions())

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2))

    r = results
    print(
        f"[engine] provider={r['providers']} regime={r['market_regime']['label']} "
        f"considered={r['universe']['considered']} "
        f"liquid={r['universe']['passed_liquidity']} "
        f"scored={r['universe']['passed_quality']} "
        f"strong_buy={r['buckets']['strong_buy']} watch={r['buckets']['watch']} "
        f"-> {out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
