"""Shared section-status text for presentation-only widgets."""

from plaivid_cli.domain.models import SectionSnapshot


def section_status(section: SectionSnapshot[object] | None) -> str:
    """Normalize a collection section status for compact display."""
    if section is None:
        return "unavailable"
    return section.status.value.replace("_", " ")
