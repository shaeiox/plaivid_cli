"""Show the Plaivid CLI version."""

import sys

from .base import CONTINUE
from .. import render
from ..version import __version__

NAME = "version"
ALIASES = ["ver"]
USAGE = "version"
DESCRIPTION = "show the Plaivid CLI version"
ORDER = 90


def run(ctx, args):
    ctx.set_status(render.info(
        "Plaivid CLI v%s   (Python %s)" % (__version__, sys.version.split()[0])))
    return CONTINUE
