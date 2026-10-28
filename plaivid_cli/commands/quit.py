"""Exit the interactive loop (session stays cached)."""

from .base import EXIT

NAME = "quit"
ALIASES = ["q", "exit"]
USAGE = "quit"
DESCRIPTION = "exit (keeps the session cached)"
ORDER = 95


def run(ctx, args):
    return EXIT
