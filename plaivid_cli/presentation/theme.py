"""Plaivid's Gemini-inspired terminal palette and presentation-only rich text.

The palette is intentionally static: monitoring freshness comes from collection
results, not a fast spinner or a decorative animation.
"""

from __future__ import annotations

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

# The reference's blue → purple → rose brand arc, applied only to the wordmark.
_BRAND_STOPS = ((71, 150, 228), (132, 122, 206), (195, 103, 127))


def _brand_color(position: int, count: int) -> str:
    step = position / max(1, count - 1) * 2
    index = min(1, int(step))
    fraction = step - index
    first, second = _BRAND_STOPS[index : index + 2]
    channels = (round(a + (b - a) * fraction) for a, b in zip(first, second, strict=True))
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def brand() -> Text:
    """Compact block mark and restrained static gradient; no extra dependencies."""
    text = Text("▝▜  ", style=f"bold {PRIMARY}")
    name = "PLAIVID"
    for index, letter in enumerate(name):
        text.append(letter, style=f"bold {_brand_color(index, len(name))}")
    text.append("  /  PVM MONITOR", style=MUTED)
    return text


def styled_metric(value: str, *, heading: bool = False) -> Text:
    """Make labels, real values, and collection states legible without ANSI markup."""
    lines = value.split("\n")
    text = Text()
    for index, line in enumerate(lines):
        if index:
            text.append("\n")
        style = f"bold {SECONDARY}" if heading or index == 0 else f"bold {ACCENT}" if index == 1 else MUTED
        text.append(line, style=style)
    # Text and color communicate status together. Avoid styling untrusted markup.
    for word, color in (
        ("ONLINE", SUCCESS), ("CURRENT", SUCCESS),
        ("WARNING", WARNING), ("STALE", WARNING), ("PARTIAL", WARNING),
        ("OFFLINE", ERROR), ("ERROR", ERROR),
        ("LOADING", PRIMARY), ("N/A", MUTED),
    ):
        text.highlight_regex(rf"\b{word}\b", style=f"bold {color}")
    return text


def apply_theme(app: App) -> None:
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
        primary=PRIMARY, secondary=SECONDARY, accent=ACCENT,
        foreground=FOREGROUND, background=BACKGROUND, surface=SURFACE,
        panel=PANEL, success=SUCCESS, warning=WARNING, error=ERROR,
        variables={"footer-key-foreground": ACCENT},
    ))
    app.theme = "plaivid-prism"
