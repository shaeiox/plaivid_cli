"""Plaivid's Gemini-inspired terminal palette and presentation-only rich text.

The palette is intentionally static: monitoring freshness comes from collection
results, not a fast spinner or a decorative animation.
"""

from __future__ import annotations

from dataclasses import dataclass

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
    "#ffffff", "#ffffff", "#ffffff", "#ffffff", "#ffffff", "#ffffff",
)


def palette_for(color_system: str | None, *, no_color: bool = False) -> Palette:
    """Select a palette for the *detected* output, never claim truecolor blindly."""
    if no_color:
        return ANSI16
    if color_system == "truecolor":
        return TRUECOLOR
    if color_system == "256":
        return ANSI256
    return ANSI16


# The reference's blue → purple → rose brand arc, applied only to the wordmark.
_BRAND_STOPS = ((71, 150, 228), (132, 122, 206), (195, 103, 127))


def _brand_color(position: int, count: int) -> str:
    step = position / max(1, count - 1) * 2
    index = min(1, int(step))
    fraction = step - index
    first, second = _BRAND_STOPS[index : index + 2]
    channels = (round(a + (b - a) * fraction) for a, b in zip(first, second, strict=True))
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def brand(palette: Palette = TRUECOLOR) -> Text:
    """Compact block mark and restrained static gradient; no extra dependencies."""
    text = Text("▝▜  ", style=f"bold {palette.primary}")
    name = "PLAIVID"
    for index, letter in enumerate(name):
        text.append(letter, style=f"bold {_brand_color(index, len(name))}" if palette is TRUECOLOR else f"bold {palette.primary}")
    text.append("  /  PVM MONITOR", style=palette.muted)
    return text


def styled_metric(value: str, *, heading: bool = False, palette: Palette = TRUECOLOR) -> Text:
    """Make labels, real values, and collection states legible without ANSI markup."""
    lines = value.split("\n")
    text = Text()
    for index, line in enumerate(lines):
        if index:
            text.append("\n")
        style = f"bold {palette.secondary}" if heading or index == 0 else f"bold {palette.accent}" if index == 1 else palette.muted
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
