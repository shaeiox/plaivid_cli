"""Validation and canonicalization of collection section requests."""

from __future__ import annotations

from collections.abc import Iterable

from plaivid_cli.domain.models import canonical_uuid

SUPPORTED_SECTIONS = frozenset(
    {
        "inventory",
        "objects",
        "processes",
        "host_status",
        "host_metrics",
        "tap_mapping",
        "dashboard",
        "desktops",
        "local_host",
        "physical_nics",
        "nic_samples",
    }
)


def normalize_sections(sections: Iterable[str]) -> tuple[str, ...]:
    """Deduplicate section demand and reject unsupported or malformed details."""
    requested = tuple(dict.fromkeys(sections))
    dynamic = {name for name in requested if name.startswith("detail:")}
    unknown = set(requested) - SUPPORTED_SECTIONS - dynamic
    if unknown:
        raise ValueError(f"unsupported collection section: {sorted(unknown)[0]}")
    for name in dynamic:
        canonical_uuid(name.split(":", 1)[1])
    if not requested:
        raise ValueError("at least one collection section is required")
    return requested
