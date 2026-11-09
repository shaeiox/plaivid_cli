"""Virtual Machine selected-record detail and audit panels."""

from __future__ import annotations

from typing import Literal

from rich.console import RenderableType
from rich.table import Table
from rich.text import Text
from textual.widgets import Static

from plaivid_cli.domain.models import VMDetail, VMRecord
from plaivid_cli.domain.redaction import redact_text
from plaivid_cli.presentation.theme import (
    TRUECOLOR,
    Palette,
    group_color,
    state_badge,
    status_badge,
)

# Placeholder states the VM page can render without a selected record.
DetailPlaceholder = Literal["empty", "no_match", "no_records", "loading", "error"]

_MISSING = "—"
# Label columns are measured from the label set, so renaming a label cannot
# silently push values out of alignment (the old f-string pane had no alignment).
_LEFT_LABELS = ("Object state", "PID", "Memory", "Machine", "Topology", "Disks / NICs")
_RIGHT_LABELS = ("Process", "vCPU", "Host", "CPU model", "Console")
_LEFT_WIDTH = max(len(label) for label in _LEFT_LABELS) + 2
_RIGHT_WIDTH = max(len(label) for label in _RIGHT_LABELS) + 2
_LEFT_VALUE_WIDTH = 18
_INDENT = _LEFT_WIDTH + 2  # label column width plus the pair grid's gutter

_PLACEHOLDERS: dict[DetailPlaceholder, tuple[str, str]] = {
    "empty": ("Select a VM to inspect its details.", "muted"),
    "no_match": ("No matching VMs. Clear search to view the inventory.", "muted"),
    "no_records": ("No VM records are currently available.", "muted"),
    "loading": ("Reading full detail…", "primary"),
    "error": ("Detail read failed · press Enter to retry", "error"),
}


def _present(value: object | None) -> str:
    """Render an absent value as an em dash, and keep one record on one line.

    Newlines from a multi-line PVM description would otherwise break the label
    column; redaction happens here, before any value becomes Rich text.
    """
    if value is None or value == "":
        return _MISSING
    text = redact_text(value)
    return text.replace("\r", " ").replace("\n", " ").replace("\t", " ")


def _format_mb(value: int | None) -> str:
    """Group megabytes for reading: 8192 -> ``8 192 MB``; absent stays an em dash."""
    if value is None:
        return _MISSING
    return f"{value:,}".replace(",", " ") + " MB"


def _label(value: str, palette: Palette) -> Text:
    return Text(value, style=palette.muted)


def _value(value: object | None, palette: Palette, *, style: str | None = None) -> Text:
    plain = _present(value)
    if plain == _MISSING:
        return Text(_MISSING, style=palette.muted)
    return Text(plain, style=style or palette.foreground)


def _process_badge(record: VMRecord, palette: Palette) -> Text:
    """Neutral process evidence marker; it must never look like a health verdict."""
    if record.process_seen:
        return status_badge("observed", palette.muted)
    return status_badge("not observed", palette.muted, glyph="○")


def _description(record: VMRecord, detail: VMDetail | None) -> str:
    description = record.object.description or (detail.description if detail else "")
    return _present(description)


def _pairs_grid(record: VMRecord, detail: VMDetail | None, palette: Palette) -> Table:
    """Aligned label/value pairs; detail-only fields stay absent until Enter reads them."""
    pid = record.process.pid if record.process is not None else None
    disks_nics = f"{len(detail.disks)} / {len(detail.nics)}" if detail is not None else None
    console = detail.console.kind if detail is not None and detail.console else None
    left = (
        ("Object state", state_badge(_present(record.state), palette)),
        ("PID", _value(pid, palette)),
        ("Memory", _value(_format_mb(record.mem_mb), palette, style=palette.accent)),
        ("Machine", _value(detail.machine if detail else None, palette)),
        ("Topology", _value(detail.vcpu_topology if detail else None, palette)),
        ("Disks / NICs", _value(disks_nics, palette)),
    )
    right = (
        ("Process", _process_badge(record, palette)),
        ("vCPU", _value(record.vcpu, palette, style=palette.accent)),
        ("Host", _value(detail.host if detail else None, palette)),
        ("CPU model", _value(detail.cpu_model if detail else None, palette)),
        ("Console", _value(console, palette)),
    )

    grid = Table.grid(padding=(0, 2))
    grid.add_column(width=_LEFT_WIDTH, no_wrap=True)
    grid.add_column(width=_LEFT_VALUE_WIDTH, no_wrap=True)
    grid.add_column(width=_RIGHT_WIDTH, no_wrap=True)
    grid.add_column(ratio=1, no_wrap=True)
    for index, (left_label, left_value) in enumerate(left):
        if index < len(right):
            right_label, right_value = right[index]
        else:
            right_label, right_value = "", Text("")
        grid.add_row(
            _label(left_label, palette),
            left_value,
            _label(right_label, palette),
            right_value,
        )
    return grid


def build_vm_detail(
    record: VMRecord, detail: VMDetail | None, palette: Palette = TRUECOLOR
) -> RenderableType:
    """Render one selected VM as an aligned, colour-coded identity block.

    ``detail`` is the optional asynchronous read triggered by Enter; when it is
    absent the fields it owns stay ``—`` rather than pretending to be empty
    readings. Every PVM-supplied string is redacted before it becomes Rich text.
    """
    identity = Text(
        redact_text(record.name),
        style=f"bold {group_color('vms', palette) or palette.foreground}",
        no_wrap=True,
        overflow="ellipsis",
    )
    uuid_line = Text(no_wrap=True)
    uuid_line.append(f"{'UUID':<{_INDENT}}", style=palette.muted)
    uuid_line.append(redact_text(record.uuid), style=palette.foreground)
    description_value = _description(record, detail)
    description = Text(no_wrap=False, overflow="fold")
    description.append(f"{'Description':<{_INDENT}}", style=palette.muted)
    description.append(
        description_value,
        style=palette.muted if description_value == _MISSING else palette.foreground,
    )

    grid = Table.grid(padding=(0, 0))
    grid.add_column()
    grid.add_row(identity)
    if record.state_disagreed:
        grid.add_row(
            Text("▲ STATE EVIDENCE CONFLICT", style=f"bold {palette.warning}", no_wrap=True)
        )
    grid.add_row(uuid_line)
    grid.add_row(_pairs_grid(record, detail, palette))
    grid.add_row(description)
    return grid


def build_detail_placeholder(kind: DetailPlaceholder, palette: Palette = TRUECOLOR) -> Text:
    """Render an empty, loading, or failed detail state in the pane's voice."""
    message, token = _PLACEHOLDERS[kind]
    return Text(message, style=getattr(palette, token))


class VMDetailPanel(Static):
    """Render selected VM identity and optional asynchronous detail fields."""

    def __init__(self) -> None:
        super().__init__(build_detail_placeholder("empty"), id="detail-box", markup=False)


class VMAuditPanel(Static):
    """Render the read-only audit result associated with the VM page."""

    def __init__(self) -> None:
        super().__init__("Read-only audit\nWaiting for session…", id="audit-panel", markup=False)
