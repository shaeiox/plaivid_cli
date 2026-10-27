"""Shared helpers and the contract every action module follows.

An action module is a tiny, self-contained file that defines:

    NAME        str   - command name typed by the user (e.g. "stop")
    ALIASES     list  - alternative names (optional)
    LABEL       str   - short title for menus
    DESCRIPTION str   - one-line help
    APPLIES_TO  set   - VM states where the action is offered (empty = always)
    DESTRUCTIVE bool  - whether to ask for confirmation
    ORDER       int   - sort order in menus
    run(ctx, vm) -> ActionResult

Keeping each action in its own file means a syntax error or bug in one never
prevents the others (or the app) from loading - see ``registry``.
"""

from .. import transport


class ActionResult(object):
    def __init__(self, ok, message):
        self.ok = ok
        self.message = message


def simple_vm_action(token, command, params):
    """Run ``vm/<command>`` and turn the reply into an ActionResult."""
    try:
        resp = transport.sbell("vm", command, params, token=token)
    except transport.TransportError as exc:
        return ActionResult(False, str(exc))
    if not resp.ok:
        return ActionResult(False, resp.error_text())
    new_state = None
    if resp.description is not None:
        new_state = resp.description.findtext("cluster_status/status")
    if new_state:
        return ActionResult(True, "now %s" % new_state)
    return ActionResult(True, "done")


def vm_key(vm):
    return "<vm_key>%s</vm_key>" % vm.uuid
