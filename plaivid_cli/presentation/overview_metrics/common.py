"""Shared text-formatting primitives for Overview telemetry presenters."""

from __future__ import annotations

from plaivid_cli.domain.redaction import redact_text

_DASH = "—"
_UNITS = ("B", "KiB", "MiB", "GiB", "TiB")
_NONE = ["No current monitoring values."]


def size(value: int | None) -> str:
    if value is None:
        return _DASH
    amount = float(value)
    for unit in _UNITS:
        if amount < 1024 or unit == _UNITS[-1]:
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return _DASH


def number(value: int | float | None, suffix: str = "") -> str:
    if value is None:
        return _DASH
    if isinstance(value, float):
        return f"{value:.1f}{suffix}"
    return f"{value:,}{suffix}"


def bar(percent: float | None, width: int = 20) -> str:
    if percent is None:
        return _DASH
    ratio = max(0, min(width, round(percent * width / 100)))
    return "█" * ratio + "░" * (width - ratio)


def pct_of(used: int | None, total: int | None) -> float | None:
    if used is None or not total:
        return None
    return 100.0 * used / total


def row(label: str, value: str) -> str:
    return f"{label:<12}: {value}"


def body(lines: list[str]) -> str:
    """Join measurement lines only and apply redaction.

    Collection status is owned by the card header, so it is intentionally *not*
    appended here: repeating "ONLINE" at the bottom of every child widget made one
    state look like several independent readings.
    """
    return redact_text("\n".join(lines))


def finish(lines: list[str], status: str) -> str:
    """Join body lines with the collection status and apply redaction.

    Retained for callers that render a standalone status line; dashboard cards
    use :func:`body` and :meth:`DashboardCard.set_status` instead.
    """
    return redact_text("\n".join([*lines, status]))
