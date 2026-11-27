"""Pause (freeze) a running VM (vm/pause)."""

from .base import simple_vm_action, vm_key

NAME = "pause"
ALIASES = ["suspend", "freeze"]
LABEL = "Pause"
DESCRIPTION = "Freeze the VM's CPUs (state kept in RAM)."
APPLIES_TO = {"started", "running"}
DESTRUCTIVE = False
ORDER = 50


def run(ctx, vm):
    return simple_vm_action(ctx.token, "pause", vm_key(vm))
