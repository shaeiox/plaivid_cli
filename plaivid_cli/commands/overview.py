"""Live monitoring page (auto-refresh until q / Ctrl-C)."""

import os
import time

from .base import CONTINUE
from .. import monitoring, render, theme, transport, vms
from ..version import __version__

NAME = "overview"
ALIASES = ["mon", "monitor", "live"]
USAGE = "overview"
DESCRIPTION = "live monitoring: CPU, load, memory, network, storage"
ORDER = 20

_SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def run(ctx, args):
    try:
        interval = max(1.0, float(os.environ.get("PLAIVID_REFRESH", "3")))
    except ValueError:
        interval = 3.0
    try:
        tapmap = vms.tap_map(ctx.token)
    except transport.TransportError:
        tapmap = {}
    frames = _SPIN if theme._unicode else "|/-\\"
    dot = theme.glyph("dot")
    prev = None
    tick = 0
    try:
        while True:
            snap = monitoring.metrics_snapshot(ctx.token)
            try:
                ctx.set_vms(vms.inventory(ctx.token))
            except transport.TransportError:
                pass
            agg = vms.aggregate(ctx.vms)
            spin = theme.primary(frames[tick % len(frames)])
            ctx.clear()
            print(render.center(render.overview(snap, prev, tapmap, agg, spin)))
            print()
            print(render.center(render.hint(
                "live monitoring  %s  refresh %gs  %s  q / Ctrl-C to exit  %s  %s"
                % (dot, interval, dot, dot,
                   theme.secondary("Plaivid CLI v" + __version__)))))
            tick += 1
            if not ctx.is_tty():
                if prev is not None:
                    break           # one-shot: second pass shows rates
                prev = snap
                time.sleep(1.0)
                continue
            prev = snap
            if not ctx.wait_or_quit(interval):
                break
    except KeyboardInterrupt:
        pass
    ctx.rendered = True
    ctx.set_status(render.hint("Exited live monitoring."))
    return CONTINUE
