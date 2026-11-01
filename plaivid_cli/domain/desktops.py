"""Distinct read-only Lite Desktop identity and observed states."""

from __future__ import annotations

from dataclasses import dataclass

from plaivid_cli.domain.models import canonical_uuid


@dataclass(frozen=True, slots=True)
class VirtualDesktop:
    uuid: str
    name: str
    enabled: str | None = None
    local_status: str | None = None
    cluster_status: str | None = None
    os_type: str | None = None
    os_version: str | None = None
    vcpu: int | None = None
    memory_size_raw: str | None = None  # No verified unit.
    parent_id: str | None = None  # Not a verified zone or owner identity.

    def __post_init__(self) -> None:
        object.__setattr__(self, "uuid", canonical_uuid(self.uuid))
        object.__setattr__(self, "name", self.name.strip() or self.uuid)
