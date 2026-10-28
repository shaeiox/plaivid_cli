"""Help - generated from both the command and action registries."""

from .base import CONTINUE
from .. import actions, render, theme

NAME = "help"
ALIASES = ["?", "h"]
USAGE = "help"
DESCRIPTION = "show this help"
ORDER = 92


def _lj(s, n):
    return s + " " * max(0, n - len(s))


def run(ctx, args):
    import plaivid_cli.commands as commands  # avoid import cycle at module load

    lines = [theme.bold("Commands")]
    for c in commands.all_commands():
        lines.append("  %s  %s" % (theme.accent(_lj(c.usage, 24)),
                                   theme.muted(c.description)))
    lines.append("  %s  %s" % (theme.accent(_lj("<action> <targets>", 24)),
                               theme.muted("run an action on one or many VMs")))
    lines.append("")
    lines.append(theme.bold("VM actions")
                 + theme.muted("  (targets: id/name, a,b,c, state:running, all)"))
    for a in actions.all_actions():
        mark = theme.warning(" !") if a.destructive else "  "
        lines.append("  %s%s %s" % (theme.accent(_lj(a.name, 10)), mark,
                                    theme.muted(a.description)))

    errs = dict(commands.load_errors)
    errs.update(actions.load_errors)
    if errs:
        lines.append("")
        lines.append(theme.error("Disabled (failed to load):"))
        for name, err in errs.items():
            lines.append("  " + theme.error("%s - %s" % (name, err)))

    ctx.set_status("\n".join(lines))
    return CONTINUE
