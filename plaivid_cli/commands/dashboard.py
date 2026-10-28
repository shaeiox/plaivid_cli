"""Reload the VM list and host status (the main dashboard)."""

from .base import CONTINUE
from .. import render

NAME = "list"
ALIASES = ["ls", "l", "refresh", "r", "status", "s"]
USAGE = "list | status | refresh"
DESCRIPTION = "reload the VM list and host status"
ORDER = 10


def run(ctx, args):
    ctx.refresh()
    ctx.request_redraw()   # interactive loop redraws anyway; one-shot draws once
    ctx.set_status(render.ok("Refreshed"))
    return CONTINUE
