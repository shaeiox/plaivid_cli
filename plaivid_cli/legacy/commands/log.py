"""Audit log viewer + analyzer."""

from .base import CONTINUE
from .. import logs, render

NAME = "log"
ALIASES = ["logs", "audit"]
USAGE = "log [N]"
DESCRIPTION = "audit log viewer + analyzer (recent actions)"
ORDER = 50


def run(ctx, args):
    limit = 40
    if args.strip().isdigit():
        limit = max(1, min(int(args.strip()), 500))
    try:
        entries = logs.recent(limit)
    except logs.LogError as exc:
        ctx.set_status(render.err("Log unavailable: %s" % exc))
        return CONTINUE
    summary = logs.summarize(entries)
    ctx.page(render.log_view(entries, summary),
             "Audit log (%d actions)" % summary["total"])
    return CONTINUE
