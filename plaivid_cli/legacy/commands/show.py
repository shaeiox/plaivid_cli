"""Detailed view of one VM."""

from .base import CONTINUE
from .. import render, transport, vms

NAME = "show"
ALIASES = ["detail", "info"]
USAGE = "show <id|name>"
DESCRIPTION = "detailed view of one VM (disks, NICs, console)"
ORDER = 40


def run(ctx, args):
    vm, err = ctx.resolve(args)
    if vm is None:
        ctx.set_status(render.err(err))
        return CONTINUE
    try:
        detail = vms.detail(ctx.token, vm)
    except transport.TransportError as exc:
        ctx.set_status(render.err("Could not read %s: %s" % (vm.name, exc)))
        return CONTINUE
    ctx.page(render.vm_detail(detail), "Viewed %s" % vm.name)
    return CONTINUE
