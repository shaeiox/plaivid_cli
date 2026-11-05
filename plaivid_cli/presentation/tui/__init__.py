"""Textual UI package, with stable names for callers and tests."""

from .app import PlaividTui
from .support import (
    CheckableTable,
    _display,
    _host_banner_text,
    _host_status_text,
    _quorum_verdict,
    _section_status,
)

__all__ = [
    "CheckableTable",
    "PlaividTui",
    "_display",
    "_host_banner_text",
    "_host_status_text",
    "_quorum_verdict",
    "_section_status",
]
