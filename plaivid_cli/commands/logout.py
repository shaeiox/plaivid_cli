"""Clear the saved session and exit."""

from .base import EXIT
from .. import render, session

NAME = "logout"
USAGE = "logout"
DESCRIPTION = "clear the saved session and exit"
ORDER = 96


def run(ctx, args):
    session.logout(ctx.session)
    print(render.ok("Session cleared."))
    return EXIT
