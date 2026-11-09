"""Plaivid's Gemini-inspired terminal palette and presentation-only rich text.

Colors are static: each card or panel group has a fixed gradient so related items
are recognisable at a glance. There is no animation; freshness comes from collection
results. Red, yellow and green are reserved for alarm, warning and OK status.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from rich.text import Text
from textual.app import App

BACKGROUND = "#1a1a2e"
SURFACE = "#2a2a3e"
PANEL = "#222238"
FOREGROUND = "#e0e0e0"
MUTED = "#a5a5ba"
BORDER = "#56546c"
PRIMARY = "#87afff"
SECONDARY = "#d7afff"
ACCENT = "#87d7d7"
SUCCESS = "#d7ffd7"
WARNING = "#ffffaf"
ERROR = "#ff87af"

@dataclass(frozen=True)
class Palette:
    """Colors shared by Textual widgets, CSS, and Rich text."""

    background: str
    surface: str
    panel: str
    foreground: str
    muted: str
    border: str
    primary: str
    secondary: str
    accent: str
    success: str
    warning: str
    error: str
    # False for 16-colour and NO_COLOR output: group gradients collapse to plain text there.
    decorative: bool = True

    def css_tokens(self) -> str:
        names = {
            "bg": self.background, "panel": self.panel, "surface": self.surface,
            "text": self.foreground, "muted": self.muted, "border": self.border,
            "blue": self.primary, "purple": self.secondary, "cyan": self.accent,
            "green": self.success, "yellow": self.warning, "rose": self.error,
        }
        return "\n".join(f"$p-{name}: {color};" for name, color in names.items()) + "\n"


TRUECOLOR = Palette(
    BACKGROUND, SURFACE, PANEL, FOREGROUND, MUTED, BORDER,
    PRIMARY, SECONDARY, ACCENT, SUCCESS, WARNING, ERROR,
)

# xterm's 256-color cube cannot express a subtle blue-black: the original
# #2a2a3e rounds to bright navy (#00005f). Separate grayscale surfaces also
# become obvious gray blocks. Keep panels and cards on the *same* canvas;
# borders and semantic text provide hierarchy without filled rectangles.
ANSI256 = Palette(
    "#121212", "#121212", "#121212", "#e4e4e4", "#b2b2b2", "#444444",
    PRIMARY, SECONDARY, ACCENT, SUCCESS, WARNING, ERROR,
)

# A 16-color terminal has no reliable RGB shades. Keep the canvas legible
# and rely on textual status labels rather than decorative color alone.
ANSI16 = Palette(
    "#000000", "#000000", "#000000", "#ffffff", "#aaaaaa", "#777777",
    "#ffffff", "#ffffff", "#ffffff", "#00ff00", "#ffff00", "#ff0000",
    decorative=False,
)

# NO_COLOR asks for no color at all; state words still carry the meaning.
NO_COLOR = replace(ANSI16, success="#ffffff", warning="#ffffff", error="#ffffff", decorative=False)

# Card and panel groups, each with a start and end colour. Hues are kept away from
# red, yellow and green so no group can be mistaken for an alarm, warning or OK state.
GROUP_STOPS: dict[str, tuple[str, str]] = {
    "host": ("#8787ff", "#d7afff"),  # violet: System information, Host status
    "compute": ("#5fafff", "#87d7ff"),  # sky: CPU, Memory, Load & tasks, Top processes
    "io": ("#ff875f", "#ffaf5f"),  # orange: Storage, Network interfaces
    "environment": ("#5fd7d7", "#afffff"),  # turquoise: Temperature, Sessions
    "vms": ("#ff87d7", "#ffafff"),  # pink: Virtual Machines and Desktops pages
}


def _rgb(colour: str) -> tuple[int, int, int]:
    value = colour.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _hex(rgb: tuple[float, float, float]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(round(channel) for channel in rgb))


def group_color(group: str, palette: Palette = TRUECOLOR) -> str | None:
    """The group's start colour, or None when colour is disabled."""
    if not palette.decorative:
        return None
    return GROUP_STOPS[group][0]


def gradient_text(value: str, start: str, end: str, *, bold: bool = True) -> Text:
    """Colour each visible character along a start-to-end gradient."""
    text = Text()
    a, b = _rgb(start), _rgb(end)
    count = max(1, len(value) - 1)
    for index, char in enumerate(value):
        t = index / count
        colour = _hex(tuple(a[i] + (b[i] - a[i]) * t for i in range(3)))
        text.append(char, style=f"bold {colour}" if bold else colour)
    return text


def group_title(group: str, title: str, palette: Palette = TRUECOLOR) -> Text:
    """A card or panel title in its group's gradient; plain text when colour is disabled."""
    if not palette.decorative:
        return Text(title, style=f"bold {palette.primary}")
    start, end = GROUP_STOPS[group]
    return gradient_text(title, start, end)


def palette_for(color_system: str | None, *, no_color: bool = False) -> Palette:
    """Select a palette for the *detected* output, never claim truecolor blindly."""
    if no_color:
        return NO_COLOR
    if color_system == "truecolor":
        return TRUECOLOR
    if color_system == "256":
        return ANSI256
    return ANSI16


def brand(palette: Palette = TRUECOLOR) -> Text:
    """Single-accent wordmark; the source readings, not a gradient, lead."""
    text = Text("▝▜  PLAIVID", style=f"bold {palette.primary}")
    text.append("  /  PVM console", style=palette.muted)
    return text


def styled_metric(value: str, *, heading: bool = False, palette: Palette = TRUECOLOR) -> Text:
    """Make labels, real values, and collection states legible without ANSI markup."""
    lines = value.split("\n")
    text = Text()
    for index, line in enumerate(lines):
        if index:
            text.append("\n")
        style = f"bold {palette.foreground}" if heading or index == 0 else f"bold {palette.accent}" if index == 1 else palette.muted
        text.append(line, style=style)
    # Text and color communicate status together. Avoid styling untrusted markup.
    for word, color in (
        ("ONLINE", palette.success), ("CURRENT", palette.success),
        ("WARNING", palette.warning), ("STALE", palette.warning), ("PARTIAL", palette.warning),
        ("OFFLINE", palette.error), ("ERROR", palette.error),
        ("LOADING", palette.primary), ("N/A", palette.muted),
    ):
        text.highlight_regex(rf"\b{word}\b", style=f"bold {color}")
    return text


# Red for "not quorate or not verifiable". Truecolor red, so it does not look like the rose error token.
ALARM = "#e53935"
# Yellow for "quorating" (cluster forming) or quorate-but-not-current.
CAUTION = "#e5c100"

# Object and cluster states, grouped by what an operator should do about them.
# Matching is exact and case-insensitive; anything unrecognized stays muted.
_HEALTHY_STATES = frozenset({"started", "running", "active", "up", "online", "ok", "quorate"})
_STOPPED_STATES = frozenset({"stopped", "shutdown", "off", "offline", "down", "failed", "error", "crashed"})
_TRANSIENT_STATES = frozenset({
    "starting", "stopping", "paused", "suspended", "migrating", "pending", "rebooting", "restarting", "degraded",
    "quorating",
})


def state_colour(value: str, palette: Palette = TRUECOLOR) -> str:
    """Resolve an object or cluster state to its semantic colour.

    This is the single classification table for states; ``state_text`` and
    ``state_badge`` (and therefore the inventory tables and the detail pane)
    cannot drift apart.
    """
    key = value.strip().lower()
    if key in _HEALTHY_STATES:
        return palette.success
    if key in _STOPPED_STATES:
        return palette.error
    if key in _TRANSIENT_STATES:
        return palette.warning
    return palette.muted


def state_text(value: str, palette: Palette = TRUECOLOR) -> Text:
    """Color an object or cluster state: started/running green, stopped red, transitional yellow."""
    return Text(value, style=f"bold {state_colour(value, palette)}")


def status_badge(value: str, colour: str, *, glyph: str = "●") -> Text:
    """A status word carrying a leading marker, so meaning never depends on colour alone."""
    return Text.assemble((f"{glyph} ", f"bold {colour}"), (value, f"bold {colour}"))


def state_badge(value: str, palette: Palette = TRUECOLOR) -> Text:
    """A state word in its semantic colour, e.g. green ``● started`` or red ``● stopped``.

    The marker and the word survive every palette, including ``NO_COLOR``, where the
    semantic colours collapse to white and only the text still carries the verdict.
    """
    return status_badge(value, state_colour(value, palette))


def apply_theme(app: App, palette: Palette = TRUECOLOR) -> None:
    """Theme Textual's *built-in* controls too, if its theme API is available.

    Older supported Textual versions still receive the explicit widget CSS.
    """
    try:
        from textual.theme import Theme
    except ImportError:
        return
    register = getattr(app, "register_theme", None)
    if register is None:
        return
    register(Theme(
        name="plaivid-prism",
        primary=palette.primary, secondary=palette.secondary, accent=palette.accent,
        foreground=palette.foreground, background=palette.background, surface=palette.surface,
        panel=palette.panel, success=palette.success, warning=palette.warning, error=palette.error,
        variables={"footer-key-foreground": palette.accent},
    ))
    app.theme = "plaivid-prism"
