"""Source and collection snapshots published by application read use cases."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Generic, TypeVar

from .enums import CollectionStatus

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class SourceResult(Generic[T]):  # noqa: UP046 — local verifier is Python 3.11
    value: T | None
    status: CollectionStatus
    source: str
    attempted_at: datetime | None = None
    succeeded_at: datetime | None = None
    error: str | None = None
    quality_issues: tuple[str, ...] = ()
    latency_seconds: float | None = None
    attempted_monotonic: float | None = None
    succeeded_monotonic: float | None = None


@dataclass(frozen=True, slots=True)
class SectionSnapshot(Generic[T]):  # noqa: UP046 — keep local Python 3.11 verification possible
    name: str
    value: T | None
    last_good_value: T | None
    status: CollectionStatus
    attempted_at: datetime | None
    succeeded_at: datetime | None
    generation: int
    source: str | None = None
    error: str | None = None
    quality_issues: tuple[str, ...] = field(default_factory=tuple)
    attempted_monotonic: float | None = None
    succeeded_monotonic: float | None = None
    latency_seconds: float | None = None

    @property
    def has_value(self) -> bool:
        return self.value is not None or self.last_good_value is not None


@dataclass(frozen=True, slots=True)
class ApplicationSnapshot:
    generation: int
    created_at: datetime
    sections: tuple[SectionSnapshot[object], ...] = ()

    def section(self, name: str) -> SectionSnapshot[object] | None:
        return next((item for item in self.sections if item.name == name), None)
