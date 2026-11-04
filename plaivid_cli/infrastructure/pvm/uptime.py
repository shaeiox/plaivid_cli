"""Derive the sballd service uptime from ``systemctl status sballd`` output."""

from __future__ import annotations

import re
from datetime import datetime

# e.g. "Active: active (running) since Wed 2026-11-04 10:27:39 +0330; 58min ago"
_SINCE = re.compile(
    r"^\s*Active:\s+active \(running\) since \w{3} (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) ([+-]\d{4});",
    re.MULTILINE,
)


def sball_started_at(status_text: str) -> datetime | None:
    match = _SINCE.search(status_text)
    if match is None:
        return None
    try:
        return datetime.strptime(" ".join(match.groups()), "%Y-%m-%d %H:%M:%S %z")
    except ValueError:
        return None


def sball_uptime_seconds(status_text: str, now: datetime) -> float | None:
    """Seconds since the service became active; None unless it is verifiably running."""
    started = sball_started_at(status_text)
    if started is None or now.tzinfo is None:
        return None
    elapsed = (now - started).total_seconds()
    return elapsed if elapsed >= 0 else None
