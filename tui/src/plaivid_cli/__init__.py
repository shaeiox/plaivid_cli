"""Plaivid CLI - a modular terminal client for PVM / Plaivid VM management.

The package is intentionally split into small, independent modules so that a
failure in one component (e.g. a single VM action) cannot take down the whole
application. See ``orchestrator`` for how the pieces are wired together.
"""

from .version import __version__

__all__ = ["__version__"]
