"""Load engine config (YAML) and environment secrets."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

try:  # optional: load .env.local for local dev
    from dotenv import load_dotenv

    for _name in (".env.local", ".env"):
        _p = Path(__file__).resolve().parents[1] / _name
        if _p.exists():
            load_dotenv(_p)
            break
except Exception:  # dotenv is optional in CI (secrets come from the environment)
    pass

CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)
    # env overrides
    lim = os.getenv("CONTEXT_UNIVERSE_LIMIT")
    if lim:
        cfg.setdefault("universe", {})["limit"] = int(lim)
    # funnel knobs (useful to bound cost in CI / local verification runs)
    for env_key, cfg_key, cast in (
        ("CONTEXT_FUNNEL_SCREEN_DAYS", "screen_days", int),
        ("CONTEXT_FUNNEL_MAX_BUCKET", "max_bucket", int),
    ):
        val = os.getenv(env_key)
        if val:
            cfg.setdefault("funnel", {})[cfg_key] = cast(val)
    return cfg


def env(key: str, default: str | None = None) -> str | None:
    return os.getenv(key, default)
