"""Overview page and its independently maintained components."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .page import OverviewPage

__all__ = ["OverviewPage"]


def __getattr__(name: str):
    if name == "OverviewPage":
        from .page import OverviewPage

        return OverviewPage
    raise AttributeError(name)
