"""Start a stopped/off VM (vm/start)."""

from .base import simple_vm_action

NAME = "start"
ALIASES = ["boot", "on"]
LABEL = "Start"
DESCRIPTION = "Power on the VM (host chosen automatically)."
APPLIES_TO = {"stopped", "off", "unknown"}
DESTRUCTIVE = False
ORDER = 10

_PARAMS = (
    "<vm_start><vm_key>%s</vm_key><host>auto</host>"
    "<version_start><version_enable>no</version_enable>"
    "<version_vkey></version_vkey></version_start>"
    "<exit_from_replicate>yes</exit_from_replicate></vm_start>"
)


def run(ctx, vm):
    return simple_vm_action(ctx.token, "start", _PARAMS % vm.uuid)
