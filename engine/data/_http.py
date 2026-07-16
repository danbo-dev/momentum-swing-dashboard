"""Shared HTTP helpers: token-bucket rate limiting + on-disk response cache."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import requests

CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache"


class RateLimiter:
    """Simple spacing limiter: at most `per_min` calls per minute."""

    def __init__(self, per_min: int):
        self._min_interval = 60.0 / max(per_min, 1)
        self._last = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        delta = now - self._last
        if delta < self._min_interval:
            time.sleep(self._min_interval - delta)
        self._last = time.monotonic()


def _cache_path(key: str) -> Path:
    h = hashlib.sha1(key.encode()).hexdigest()[:16]
    return CACHE_DIR / f"{h}.json"


def cached_get(
    url: str,
    params: dict,
    limiter: RateLimiter,
    ttl_hours: float,
    cache_key: str | None = None,
    timeout: int = 30,
) -> dict:
    """GET with disk cache (keyed by url+params or an explicit key) and rate limiting."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = cache_key or (url + "?" + json.dumps(params, sort_keys=True))
    cp = _cache_path(key)
    if cp.exists() and (time.time() - cp.stat().st_mtime) < ttl_hours * 3600:
        try:
            return json.loads(cp.read_text())
        except Exception:
            pass

    limiter.wait()
    for attempt in range(4):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            if resp.status_code == 429:  # rate limited: back off
                time.sleep(2 ** attempt * 5)
                continue
            resp.raise_for_status()
            data = resp.json()
            cp.write_text(json.dumps(data))
            return data
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError(f"GET failed after retries: {url}")
