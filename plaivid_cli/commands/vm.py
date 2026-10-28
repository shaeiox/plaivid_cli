"""VM Management Page - full-screen VM list with pagination, search, and sort.

Triggered by the ``vm`` (or ``virtualmachine``) command. Renders a paginated
VM table with live search (`/` key), sorting, and arrow-key navigation.
Exit with ``q`` or ``Esc`` to return to the main command prompt.
"""

from .base import CONTINUE

from .. import render, theme


NAME = "vm"
ALIASES = ["virtualmachine", "vms"]
USAGE = "vm"
DESCRIPTION = "VM management page: paginated list, search, sort"
ORDER = 35


_KEYS_HELP = [
    theme.bold("VM Management Page"),
    theme.muted("Keys:"),
    "  Up/Down   Move selection cursor (wraps to prev/next page)",
    "  PgUp/PgDn Previous / next page of VMs",
    "  /         Live search (filters Name, ID, State, UUID)",
    "  Esc       Clear search / cancel",
    "  q         Return to command prompt",
]


def run(ctx, args):
    """Enter the VM management page."""
    app = ctx.app
    app.run_vm_management()
    ctx.set_status("\n".join(_KEYS_HELP))
    return CONTINUE
