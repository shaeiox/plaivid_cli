"""Textual frontend package with lazy stable exports for the app and shared widgets."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .app import PlaividTui

_SUPPORT_EXPORTS = {
    "CheckableTable",
    "_display",
    "_host_banner_text",
    "_host_status_text",
    "_quorum_verdict",
    "_section_status",
}

__all__ = [
    "CheckableTable",
    "PlaividTui",
    "_display",
    "_host_banner_text",
    "_host_status_text",
    "_quorum_verdict",
    "_section_status",
]


def __getattr__(name: str):
    if name == "PlaividTui":
        return import_module(".app", __name__).PlaividTui
    if name in _SUPPORT_EXPORTS:
        return getattr(import_module(".support", __name__), name)
    raise AttributeError(name)
