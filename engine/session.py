"""Trading-session resolution — the scan's single definition of "now".

A scan is not a point in time; on the free tier a cold run takes ~2 hours. If each
fetch decides for itself what "today" means, a run that straddles the 16:00 ET close
caches a mix of intraday snapshots and real closes under one calendar-date key, and
the next run happily reuses the blend. That is exactly the corruption this module
exists to prevent.

So: resolve the session ONCE at the top of a run, thread it through every fetch, and
key caches on it. Then run duration, cron lag, queueing and DST stop mattering — a
fetch at 14:39 and one at 16:51 describe the same session or they are not used.

The session is "the most recent completed regular session as of `now`". Intraday, that
is the prior trading day; after the close (plus a settle margin) it is today.
"""
from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

MARKET_TZ = ZoneInfo("America/New_York")
REGULAR_CLOSE = time(16, 0)
# Consolidated-tape prints settle a few minutes after the bell; don't call a session
# complete the instant it closes.
SETTLE_MINUTES = 15

# US market holidays that fall on weekdays. Missing entries are harmless: the fetch
# layer skips empty sessions anyway, this only sharpens which date we label the run.
_HOLIDAYS_2026 = {
    date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3),
    date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7),
    date(2026, 11, 26), date(2026, 12, 25),
}


def is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d not in _HOLIDAYS_2026


def previous_trading_day(d: date) -> date:
    d -= timedelta(days=1)
    while not is_trading_day(d):
        d -= timedelta(days=1)
    return d


def resolve_session(now: datetime | None = None) -> date:
    """The session this scan is ABOUT — the last completed regular session.

    Override with SESSION_DATE=YYYY-MM-DD for backfills and reproducible tests.
    """
    override = os.getenv("SESSION_DATE")
    if override:
        return date.fromisoformat(override.strip())

    now = (now or datetime.now(timezone.utc)).astimezone(MARKET_TZ)
    today = now.date()
    closed = (
        is_trading_day(today)
        and now.time() >= (datetime.combine(today, REGULAR_CLOSE)
                           + timedelta(minutes=SETTLE_MINUTES)).time()
    )
    return today if closed else previous_trading_day(today)


def session_is_current(session: date, now: datetime | None = None) -> bool:
    """True when `session` is the latest completed one — i.e. the run is not stale.
    False means the scan fired before the close and is reporting the prior session."""
    return session == resolve_session(now)
