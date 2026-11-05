"""Supported one-shot CLI front end, exported through a stable module API."""

from .dispatch import run_command
from .operations import EXIT_FAILURE, EXIT_OK, EXIT_PARTIAL, EXIT_REJECTED, EXIT_UNKNOWN
from .parser import build_parser
from .serialization import configuration_command

__all__ = [
    "EXIT_FAILURE",
    "EXIT_OK",
    "EXIT_PARTIAL",
    "EXIT_REJECTED",
    "EXIT_UNKNOWN",
    "build_parser",
    "configuration_command",
    "run_command",
]
