"""Freshness policy for mutable collection sections."""

from __future__ import annotations

import time

from plaivid_cli.domain.models import CollectionStatus, SectionSnapshot


def section_is_fresh(
    section: SectionSnapshot[object] | None,
    max_age_seconds: float | None,
    *,
    now: float | None = None,
) -> bool:
    """Only a current section with a monotonic success timestamp can be fresh."""
    if (
        section is None
        or max_age_seconds is None
        or max_age_seconds <= 0
        or section.status is not CollectionStatus.CURRENT
        or section.succeeded_monotonic is None
    ):
        return False
    current = time.monotonic() if now is None else now
    return max(0.0, current - section.succeeded_monotonic) <= max_age_seconds
