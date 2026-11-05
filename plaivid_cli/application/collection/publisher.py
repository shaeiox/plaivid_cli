"""Last-good section publication policy for completed local collection requests."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime

from plaivid_cli.domain.models import (
    ApplicationSnapshot,
    CollectionStatus,
    SectionSnapshot,
    SourceResult,
)


def stale_after_mutation(
    prior: SectionSnapshot[object],
    section_name: str,
    *,
    generation: int,
    attempted_at: datetime,
    attempted_monotonic: float,
) -> SectionSnapshot[object]:
    """Invalidate a previously published collection section after a mutation."""
    return SectionSnapshot(
        name=section_name,
        value=None,
        last_good_value=(
            prior.last_good_value if prior.last_good_value is not None else prior.value
        ),
        status=CollectionStatus.STALE,
        attempted_at=attempted_at,
        succeeded_at=prior.succeeded_at,
        generation=generation,
        source=prior.source,
        error=f"{section_name} requires post-operation reconciliation",
        quality_issues=prior.quality_issues,
        attempted_monotonic=attempted_monotonic,
        succeeded_monotonic=prior.succeeded_monotonic,
    )


def publish_results(
    sections: dict[str, SectionSnapshot[object]],
    results: dict[str, SourceResult[object]],
    *,
    generation: int,
    current_epoch: int,
    mutation_epoch: int,
    started_at: datetime,
    started_mono: float,
    snapshot_factory: Callable[[], ApplicationSnapshot],
) -> ApplicationSnapshot:
    """Publish results unless a mutation invalidated the read generation.

    The caller must hold the collection coordinator's reentrant lock throughout this call.
    """
    if mutation_epoch != current_epoch:
        return snapshot_factory()

    for name, result in results.items():
        prior = sections.get(name)
        previous_value = (
            (prior.last_good_value if prior.last_good_value is not None else prior.value)
            if prior
            else None
        )
        success = result.value is not None and result.status in {
            CollectionStatus.CURRENT,
            CollectionStatus.PARTIAL,
        }
        value = result.value if success else None
        last_good = result.value if success else previous_value
        status = result.status
        if not success and previous_value is not None and status is not CollectionStatus.NEVER:
            status = CollectionStatus.STALE
        succeeded_at = (
            result.succeeded_at or datetime.now(UTC)
            if success
            else prior.succeeded_at
            if prior
            else None
        )
        succeeded_mono = (
            result.succeeded_monotonic or time.monotonic()
            if success
            else prior.succeeded_monotonic
            if prior
            else None
        )
        sections[name] = SectionSnapshot(
            name=name,
            value=value,
            last_good_value=last_good,
            status=status,
            attempted_at=result.attempted_at or started_at,
            succeeded_at=succeeded_at,
            generation=generation,
            source=result.source or (prior.source if prior else None),
            error=result.error,
            quality_issues=result.quality_issues,
            attempted_monotonic=result.attempted_monotonic or started_mono,
            succeeded_monotonic=succeeded_mono,
            latency_seconds=(
                result.latency_seconds if success else prior.latency_seconds if prior else None
            ),
        )
    return snapshot_factory()
