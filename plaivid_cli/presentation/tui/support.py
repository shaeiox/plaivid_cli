"""Small reusable Textual widgets and pure status-formatting helpers."""

from __future__ import annotations

from rich.text import Text
from textual import events
from textual.message import Message
from textual.widgets import DataTable

from plaivid_cli.domain.models import Action, CollectionStatus, HostStatus, SectionSnapshot
from plaivid_cli.domain.redaction import redact_text
from plaivid_cli.presentation.theme import ALARM, CAUTION, TRUECOLOR

DESKTOP_MIN_REFRESH_SECONDS = 15.0  # Conservative provisional cadence; manual Refresh is explicit.

_METRIC_PANELS = (
    "metrics-system",
    "metrics-network",
    "metrics-storage",
    "metrics-temperature",
    "metrics-sessions",
    "metrics-processes",
    "metrics-commands",
)
BULK_ACTIONS: tuple[Action, ...] = (
    Action.START,
    Action.RESUME,
    Action.PAUSE,
    Action.STOP,
    Action.RESET,
    Action.KILL,
)


def _action_label(action: Action) -> str:
    return action.value.title()


class CheckableTable(DataTable):
    """Row table whose first column is a selection checkbox. Clicking it posts ``CheckRequested``."""

    class CheckRequested(Message):
        def __init__(self, table: CheckableTable, key: str) -> None:
            super().__init__()
            self.table = table
            self.key = key

    async def _on_click(self, event: events.Click) -> None:
        meta = event.style.meta
        if meta.get("column") == 0 and "row" in meta and not meta.get("out_of_bounds", False):
            rows = self.ordered_rows
            index = meta["row"]
            if 0 <= index < len(rows):
                key = rows[index].key
                self.post_message(self.CheckRequested(self, str(getattr(key, "value", key))))
            return
        await super()._on_click(event)


def _display(value: int | float | str | None, *, suffix: str = "") -> str:
    return "—" if value is None else f"{value}{suffix}"


def _section_status(section: SectionSnapshot[object] | None) -> str:
    if section is None:
        return "unavailable"
    return section.status.value.replace("_", " ")


def _quorum_verdict(
    section: SectionSnapshot[object] | None, palette=TRUECOLOR, pid_file: bool | None = None
) -> tuple[str, str, str]:
    """Quorum verdict from the *live* read only: (level, banner, colour).

    level is ``ok`` (current and quorate), ``warn`` (quorate but partial or stale) or ``bad``
    (not quorate, or not verifiable). A failed read never keeps the last good value as current.
    When the read fails and the sballd PID file is missing, the service is reported as not operational.
    """
    if section is None:
        return "bad", "SBALL NOT VERIFIED · no status", ALARM
    live = section.value if isinstance(section.value, HostStatus) else None
    collection = section.status.value.replace("_", " ")
    if live is None:
        if pid_file is False:
            return "bad", "SBALL NOT OPERATIONAL · PID file missing, sbell not responding", ALARM
        return "bad", f"SBALL NOT VERIFIED · {collection}", ALARM
    state = (live.sball_state or "").strip().lower()
    if state == "quorate" and section.status is CollectionStatus.CURRENT:
        return "ok", "SBALL QUORATE", palette.success
    if state == "quorating":
        # Cluster is forming: not yet quorate, so not red either.
        suffix = "" if section.status is CollectionStatus.CURRENT else f" · {collection}"
        return "warn", f"SBALL QUORATING{suffix}", CAUTION
    if state == "quorate":
        return "warn", f"SBALL QUORATE · {collection}", CAUTION
    return "bad", f"SBALL NOT QUORATE · {live.sball_state or 'state unknown'}", ALARM


def _host_banner_text(
    section: SectionSnapshot[object] | None,
    palette=TRUECOLOR,
    pid_file: bool | None = None,
) -> Text:
    """Centered quorum banner under the logo; colour comes from the live verdict."""
    _, banner, colour = _quorum_verdict(section, palette, pid_file)
    return Text(redact_text(banner), style=f"bold {colour}")


def _host_status_text(
    status: HostStatus | None,
    section: SectionSnapshot[object] | None,
    palette=TRUECOLOR,
    pid_file: bool | None = None,
    label_colour: str | None = None,
) -> Text:
    """Aligned ``label : value`` rows under the banner. Live values only are coloured as status."""
    live = section.value if isinstance(section.value, HostStatus) else None
    text = Text()
    if status is None:
        text.append(redact_text("No current host-status values."), style=palette.muted)
        return text
    rows = (
        ("Node", status.name or "—"),
        ("IP", status.ip or "—"),
        ("Version", status.version or "—"),
    )
    for label, value in rows:
        text.append(
            f"{label:<8} : ", style=f"bold {label_colour}" if label_colour else palette.muted
        )
        text.append(
            redact_text(value),
            style=f"bold {palette.accent}" if label == "Version" and live else None,
        )
        text.append("\n")
    if live is None:
        # Last known values are labelled as such and never coloured as live status.
        text.append(redact_text("(last known)"), style=palette.muted)
    return text
