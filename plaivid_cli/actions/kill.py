"""Force power-off a running VM (vm/kill - no graceful shutdown)."""

from .base import simple_vm_action, vm_key

NAME = "kill"
ALIASES = ["poweroff", "force-stop"]
LABEL = "Kill"
DESCRIPTION = "Forced power-off (pulls the plug - no guest shutdown)."
APPLIES_TO = {"started", "running"}
DESTRUCTIVE = True
ORDER = 30


def run(ctx, vm):
    return simple_vm_action(ctx.token, "kill", vm_key(vm))
