"""Read-only audit domain records."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuditEntry:
    time: str
    user: str
    user_ip: str
    product: str
    command: str
    result: str
    succeeded: bool


@dataclass(frozen=True, slots=True)
class AuditSummary:
    total: int
    failures: int
    top_commands: tuple[tuple[str, int], ...]
    top_users: tuple[tuple[str, int], ...]
    span: tuple[str | None, str | None]
