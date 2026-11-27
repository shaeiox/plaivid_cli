"""Presentation-side DTO validation and adaptation; no Engine imports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SectionDTO:
    status: str
    value: Any = None
    error: str | None = None
    age_seconds: float | None = None
    generation: int | None = None

    @classmethod
    def from_wire(cls, value: object) -> SectionDTO | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("invalid section DTO")
        status = value.get("status")
        if not isinstance(status, str):
            raise ValueError("invalid section status")
        age = value.get("age_seconds")
        generation = value.get("generation")
        if age is not None and (isinstance(age, bool) or not isinstance(age, (int, float))):
            age = None
        if generation is not None and (
            isinstance(generation, bool) or not isinstance(generation, int)
        ):
            generation = None
        error = value.get("error") if isinstance(value.get("error"), str) else None
        return cls(status, value.get("value"), error, age, generation)


@dataclass(frozen=True, slots=True)
class SnapshotDTO:
    generation: int
    sections: dict[str, SectionDTO]

    @classmethod
    def from_wire(cls, value: object) -> SnapshotDTO:
        if (
            not isinstance(value, dict)
            or not isinstance(value.get("generation"), int)
            or not isinstance(value.get("sections"), dict)
        ):
            raise ValueError("invalid snapshot DTO")
        sections = {
            key: dto
            for key, raw in value["sections"].items()
            if isinstance(key, str)
            if (dto := SectionDTO.from_wire(raw)) is not None
        }
        return cls(value["generation"], sections)

    def section(self, name: str) -> SectionDTO | None:
        return self.sections.get(name)
