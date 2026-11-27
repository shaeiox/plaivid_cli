"""Command contract + the context facade passed to every command.

A command module is a self-contained file that defines:

    NAME        str   - verb typed by the user (e.g. "health")
    ALIASES     list  - alternative names (optional)
    USAGE       str   - short usage shown in help (optional; defaults to NAME)
    DESCRIPTION str   - one-line help
    ORDER       int   - sort order in help/menus
    COMPLETE    list  - Tab-completion words for the argument (optional;
                        defaults to VM names / indexes)
    run(ctx, args) -> CONTINUE | EXIT

``run`` receives a ``CommandContext`` (a stable, narrow view of the app) and
the raw argument string. It returns EXIT to end the interactive loop, else
CONTINUE. Keeping each verb in its own file means one can be added, removed or
broken without affecting the others - see the registry in ``__init__``.
"""

import sys

from .. import vms

CONTINUE = "continue"
EXIT = "exit"


class CommandContext(object):
    """Everything a command may touch, and nothing it shouldn't.

    Commands go through this facade instead of reaching into ``App`` directly,
    so the app's internals can change without breaking command files.
    """

    def __init__(self, app):
        self._app = app
        self.rendered = False   # a full-screen page was drawn this dispatch
        self.redraw = False     # the dashboard should be redrawn (one-shot)

    def reset(self):
        self.rendered = False
        self.redraw = False

    # --- app state ----------------------------------------------------------
    @property
    def app(self):
        return self._app

    @property
    def token(self):
        return self._app.ctx.token

    @property
    def session(self):
        return self._app.session

    @property
    def host(self):
        return self._app.host

    @property
    def vms(self):
        return self._app.vms

    def set_vms(self, value):
        self._app.vms = value

    # --- status / screen ----------------------------------------------------
    def refresh(self):
        self._app.refresh()

    def set_status(self, status):
        self._app.status = status

    def request_redraw(self):
        self.redraw = True

    def clear(self):
        self._app._clear()

    def is_tty(self):
        return sys.stdin.isatty()

    def page(self, body, note):
        """Show a full-screen page (waits for Enter on a TTY)."""
        self._app._page(body, note)
        self.rendered = True

    def wait_or_quit(self, interval):
        return self._app._wait_or_quit(interval)

    # --- VM list ordering ---------------------------------------------------
    def get_sort(self):
        return self._app.sort_key, self._app.sort_desc

    def set_sort(self, key, desc=False):
        """Set the VM-list order (kept across refreshes) and apply it now."""
        self._app.sort_key, self._app.sort_desc = key, desc
        self._app.vms = vms.sort_vms(self._app.vms, key, desc)

    # --- VM resolution ------------------------------------------------------
    def resolve(self, selector):
        return vms.resolve(self._app.vms, selector)

    def resolve_many(self, selector):
        return vms.resolve_many(self._app.vms, selector)
