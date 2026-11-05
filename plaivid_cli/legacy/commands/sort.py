"""Sort the VM list by a column (persists across refreshes)."""

from .base import CONTINUE
from .. import render, vms

NAME = "sort"
USAGE = "sort [field] [asc|desc]"
DESCRIPTION = "sort the VM list: name, state, cpu, mem, uptime, pid, port, uuid (sort reset)"
ORDER = 15

_FIELD_ALIASES = {
    "vcpu": "cpu", "memory": "mem", "ram": "mem",
    "spice": "port", "console": "port",
    "reset": "index", "default": "index", "#": "index",
}
_DESC = ("desc", "d", "down", "-")
_ASC = ("asc", "a", "up", "+")

COMPLETE = sorted(set(vms.SORT_KEYS) | set(_FIELD_ALIASES) | {"asc", "desc"})


def _fields():
    return ", ".join(sorted(k for k in vms.SORT_KEYS if k != "index"))


def run(ctx, args):
    parts = args.lower().split()
    if not parts:
        key, desc = ctx.get_sort()
        ctx.set_status(render.info("Sorted by %s (%s). Fields: %s"
                                   % (key or "default", "desc" if desc else "asc",
                                      _fields())))
        return CONTINUE

    field = _FIELD_ALIASES.get(parts[0], parts[0])
    if field not in vms.SORT_KEYS:
        ctx.set_status(render.err("Unknown sort field '%s'. Use: %s"
                                  % (parts[0], _fields())))
        return CONTINUE
    direction = parts[1] if len(parts) > 1 else ""
    if direction and direction not in _DESC + _ASC:
        ctx.set_status(render.err("Direction must be asc or desc"))
        return CONTINUE

    desc = direction in _DESC
    ctx.set_sort(None if field == "index" else field, desc)
    ctx.request_redraw()
    if field == "index":
        ctx.set_status(render.ok("Sort reset (running first, then by name)"))
    else:
        ctx.set_status(render.ok("Sorted by %s (%s)"
                                 % (field, "desc" if desc else "asc")))
    return CONTINUE
