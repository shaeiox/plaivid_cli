"""UI-only entry point; application capabilities are fetched over local IPC."""

from __future__ import annotations

import sys

from .engine_client.client import EngineClient


def main() -> int:
    if not sys.stdin.isatty():
        print("plaivid: the Textual interface requires an interactive terminal", file=sys.stderr)
        return 2
    from .presentation.tui.app import PlaividTui

    PlaividTui(EngineClient()).run()
    return 0
