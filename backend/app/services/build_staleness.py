"""Shared rule for "is this audiobook build stuck?".

A build that is queued / extracting / synthesizing is considered stale when its
row has not been touched for STALE_AFTER. The worker touches the row while it
makes progress, so a healthy long build never becomes stale.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

STALE_AFTER = timedelta(minutes=30)


def is_stale(updated_at: datetime | None, now: datetime | None = None) -> bool:
    """True when ``updated_at`` is missing or older than STALE_AFTER (naive = UTC)."""
    if updated_at is None:
        return True
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return (now or datetime.now(timezone.utc)) - updated_at > STALE_AFTER
