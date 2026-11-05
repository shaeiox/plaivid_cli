"""Hard-reset a running VM (vm/reset)."""

from .base import simple_vm_action, vm_key

NAME = "reset"
ALIASES = ["restart", "reboot"]
LABEL = "Reset"
DESCRIPTION = "Hard reset (like the physical reset button)."
APPLIES_TO = {"started", "running"}
DESTRUCTIVE = True
ORDER = 40


def run(ctx, vm):
    return simple_vm_action(ctx.token, "reset", vm_key(vm))
