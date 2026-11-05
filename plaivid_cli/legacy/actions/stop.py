"""Gracefully stop a running VM (vm/stop - ACPI shutdown)."""

from .base import simple_vm_action, vm_key

NAME = "stop"
ALIASES = ["shutdown"]
LABEL = "Stop"
DESCRIPTION = "Graceful ACPI shutdown of a running VM."
APPLIES_TO = {"started", "running"}
DESTRUCTIVE = True
ORDER = 20


def run(ctx, vm):
    return simple_vm_action(ctx.token, "stop", vm_key(vm))
