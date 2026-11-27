"""Plain-text projection of a Rich-rendering TUI widget for test assertions."""

from __future__ import annotations

import io

from rich.console import Console


def plain(widget: object, *, width: int = 120) -> str:
    """Return the widget's current content as plain text.

    ``Static.render()`` returns a Rich ``Text``/Textual ``Content`` for simple
    strings and a ``RichVisual`` wrapping a ``Table`` for the structured detail
    pane. Normalise all of those so assertions can stay about copy and columns.
    """
    renderable = widget.render()  # type: ignore[attr-defined]
    for _ in range(3):
        inner = getattr(renderable, "_renderable", None)
        if inner is None:
            break
        renderable = inner
    text = getattr(renderable, "plain", None)
    if isinstance(text, str):
        return text
    buffer = io.StringIO()
    Console(file=buffer, width=width, color_system=None).print(renderable)
    return buffer.getvalue()
