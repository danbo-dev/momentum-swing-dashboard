"""Entry point: run the scan and write data/results.json.

Usage:
    python -m engine              # run scan -> data/results.json
    python -m engine --out path   # custom output path
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .pipeline import run_scan

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "web" / "public" / "data"
DEFAULT_OUT = DATA_DIR / "results.json"


def _load_positions() -> list[dict]:
    p = DATA_DIR / "positions.json"
    if p.exists():
        try:
            return json.loads(p.read_text()).get("positions", [])
        except Exception:
            return []
    return []


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
