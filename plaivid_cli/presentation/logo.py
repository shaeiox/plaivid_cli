"""Plaivid logo as terminal block art, traced from assets/plaivid-logo.svg.

Terminals cannot display SVG, so the card shows this rendering of the same logo.
Regenerate it from the SVG source when the logo changes.
"""

from __future__ import annotations

from rich.text import Text

# Logo colour sampled from the source PNG.
LOGO_COLOR = "#7bb54d"

LOGO_ROWS: tuple[str, ...] = (
    "                ▄██▄                ",
    "        ▄▄      ████     ▄▄▄        ",
    "       ████▄    ████   ▄█████       ",
    "        ▀████▄  ████ ▄█████▀        ",
    "   ▄▄▄▄   ▀████▄    █████▀   ▄▄▄▄   ",
    "   ████▄    ▀████▄▄████▀   ▄█████   ",
    "    ▀████▄    ▀██████▀   ▄█████▀    ",
    "      ▀████▄    ▀██▀   ▄█████▀      ",
    " ▄▄▄▄▄▄ ▀████▄       ▄█████▀ ▄▄▄▄▄  ",
    "████████  ▀████▄    ▄████▀  ████████",
    "▀▀▀▀▀▀▀▀ ▄████▀      █████▄ ▀▀▀▀▀▀▀▀",
    "       ▄█████   ▄██▄  ▀█████▄       ",
    "     ▄█████▀    ████    ▀█████▄     ",
    "   ▄█████▀      ████      ▀█████▄   ",
    "   ████▀        ████        ▀████   ",
    "                ████                ",
    "                ████                ",
    "                ████                ",
    "                ▀██▀                ",
)


def logo_text(color: str = LOGO_COLOR) -> Text:
    """The logo as Rich text, one line per terminal row; green normally, red when Sball is not quorate."""
    return Text("\n".join(LOGO_ROWS), style=f"bold {color}")
