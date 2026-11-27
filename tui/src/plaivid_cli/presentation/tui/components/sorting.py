"""Column sorting shared by the VM and Desktop inventory tables.

Sorting happens here, in Python, rather than through ``DataTable.sort``: the
pages own row order through ``_table_order``/``_desktop_rows`` and re-add rows
whenever it changes, so the operator's choice has to be part of that key or the
cursor, the checkboxes and the visible rows would disagree after a sort.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")

# Sortable columns per table. Index 0 (the checkbox) and the VM page's
# regenerated index column are deliberately absent, so header clicks on them
# cannot reorder anything. Values are the header labels shown to the operator.
VM_SORT_COLUMNS: dict[int, str] = {
    2: "VM name",
    3: "Object state",
    4: "Process",
    5: "vCPU",
    6: "Memory",
}
DESKTOP_SORT_COLUMNS: dict[int, str] = {
    1: "Desktop",
    2: "UUID",
    3: "Cluster status",
    4: "OS",
    5: "vCPU",
}

# The sort state carried on the app: the chosen column and its direction, or
# ``None`` for the page's own default order.
SortState = tuple[int, bool] | None


def next_sort_state(
    current: SortState, column: int, sortable: dict[int, str]
) -> SortState:
    """Cycle a column: ascending -> descending -> the page default.

    Clicking a different column always starts at ascending, so the first click
    on a header answers "sort by this" without any extra keystrokes.
    """
    if column not in sortable:
        return current  # Unsorted column (✓ / #): leave the order untouched.
    if current is None or current[0] != column:
        return (column, False)
    if not current[1]:
        return (column, True)
    return None


def describe_sort(state: SortState, sortable: dict[int, str]) -> str:
    """Human-readable sort description for a panel title, e.g. ``sorted by vCPU ▼``."""
    if state is None or state[0] not in sortable:
        return ""
    return f"sorted by {sortable[state[0]]} {'▼' if state[1] else '▲'}"


@dataclass(frozen=True)
class SortOutcome:
    """The order to render plus the sort state actually applied.

    ``applied`` is ``None`` when no column sort is active *or* when the chosen
    column has no comparable value in this dataset (an all-missing column), so
    the caller can fall back to its default order instead of pinning rows to a
    meaningless alphabetical sequence.
    """

    records: list
    applied: SortState


def sort_records(
    records: list[T],
    state: SortState,
    default_key: Callable[[T], object],
    column_keys: dict[int, Callable[[T], object]],
) -> SortOutcome:
    """Order ``records`` by the operator's column choice, else by ``default_key``.

    ``column_keys`` supplies a column's sort value: a string, an int, or any
    tuple whose first element flags a missing value. Missing values sort last in
    *both* directions — that flag is never reversed — while ``uuid`` (the last
    element of every column key) breaks ties deterministically in both cases.
    """
    if state is not None and state[0] in column_keys:
        key = column_keys[state[0]]
        if any(_has_value(key(record)) for record in records):
            # Direction applies to the value, not to presence: reversing the
            # whole key would float absent values to the top when descending.
            # Two stable passes keep them last in both directions.
            ordered = sorted(records, key=key, reverse=state[1])
            ordered = sorted(ordered, key=lambda record: not _has_value(key(record)))
            return SortOutcome(ordered, state)
    return SortOutcome(sorted(records, key=default_key), None)


def _has_value(key: object) -> bool:
    """True unless a column key's leading missing-value flag is set."""
    if isinstance(key, tuple) and key:
        return not key[0]
    return True


def column_value(
    value: object,
    identifier: str,
    *,
    numeric: bool = False,
    fold: bool = True,
) -> str | int | tuple[bool, str | int, str]:
    """A comparable value for one cell, keeping absent data last.

    Absent values (``None``, ``""``) become ``(True, …)`` so they sort after
    every present value whichever direction the operator chooses; ``numeric``
    keeps ``2 < 10`` instead of the text order ``"10" < "2"``.
    """
    if value is None or value == "":
        return (True, 0 if numeric else "", identifier)
    if numeric:
        return (False, int(value), identifier)  # type: ignore[arg-type]
    text = str(value)
    return (False, text.casefold() if fold else text, identifier)
