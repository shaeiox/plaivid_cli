"""Live host quorum status card."""

from rich.console import RenderableType
from rich.text import Text
from textual.app import ComposeResult
from textual.widgets import Static

from plaivid_cli.domain.models import CollectionStatus, HostStatus, SectionSnapshot
from plaivid_cli.domain.redaction import redact_text
from plaivid_cli.presentation.theme import ALARM, CAUTION, TRUECOLOR, Palette
from plaivid_cli.presentation.tui.components import DashboardCard


class HostStatusCard(DashboardCard):
    """Show the live host identity verdict and status rows supplied by the page controller."""

    def __init__(self, palette: Palette) -> None:
        super().__init__(id="host-status-box", group="host", title="Host status", palette=palette)

    def compose(self) -> ComposeResult:
        yield Static("", id="host-logo", markup=False)
        yield Static("", id="host-banner", markup=False)
        yield Static("Waiting for collection…", id="host-status", markup=False)

    def set_logo(self, value: RenderableType) -> None:
        self.query_one("#host-logo", Static).update(value)

    def set_banner(self, value: RenderableType) -> None:
        self.query_one("#host-banner", Static).update(value)

    def set_details(self, value: RenderableType) -> None:
        self.query_one("#host-status", Static).update(value)


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
