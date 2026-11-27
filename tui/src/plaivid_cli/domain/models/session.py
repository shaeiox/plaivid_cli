"""Authenticated PVM session value."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class PvmSession:
    username: str
    token: str = field(repr=False)
    authenticated_at: datetime | None = None
