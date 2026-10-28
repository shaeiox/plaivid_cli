"""Health & capacity summary."""

from .base import CONTINUE
from .. import monitoring, render, vms

NAME = "health"
ALIASES = ["hc"]
USAGE = "health"
DESCRIPTION = "health & capacity summary (quorum, pressure, overcommit, license)"
ORDER = 30


def run(ctx, args):
    snap = monitoring.metrics_snapshot(ctx.token)
    if snap.get("error"):
        ctx.set_status(render.err("Health unavailable: %s" % snap["error"]))
        return CONTINUE
    agg = vms.aggregate(ctx.vms)
    lic = monitoring.license_info(ctx.token)
    report = monitoring.health_report(snap, agg, lic, ctx.host)
    ctx.page(render.health(report), "Health: %s" % report["verdict"].upper())
    return CONTINUE
