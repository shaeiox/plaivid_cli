"""Resume a paused VM (vm/resume)."""

from .base import simple_vm_action, vm_key

NAME = "resume"
ALIASES = ["unpause", "continue"]
LABEL = "Resume"
DESCRIPTION = "Un-freeze a paused VM."
APPLIES_TO = {"started", "running", "paused"}
DESTRUCTIVE = False
ORDER = 60


def run(ctx, vm):
    return simple_vm_action(ctx.token, "resume", vm_key(vm))
