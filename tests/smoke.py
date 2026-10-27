"""Non-interactive smoke test for the data layer (run on the PVM host).

Logs in with PLAIVID_PASS, then exercises session, monitoring, inventory,
resolve and the action registry WITHOUT changing any VM state.

    PLAIVID_PASS='...' python3 tests/smoke.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plaivid_cli import actions, monitoring, session, vms  # noqa: E402


def main():
    pw = os.environ.get("PLAIVID_PASS")
    user = os.environ.get("PLAIVID_USER", "manage")
    if not pw:
        print("set PLAIVID_PASS"); return 2

    print("== login ==")
    s = session.login(user, pw)
    print("  ok, user=%s claims=%s" % (s.username, s.claims()))

    print("== host status ==")
    h = monitoring.host_status(s.token)
    if h.get("error"):
        print("  ERROR:", h["error"])
    else:
        print("  %s %s  cpu=%.0f%% ram=%.0f%% load=%s" % (
            h.get("name"), h.get("version"),
            h.get("cpu_pct") or 0, h.get("ram_pct") or 0, h.get("load1")))

    print("== inventory ==")
    inv = vms.inventory(s.token)
    for v in inv:
        print("  %2d %-26s %-9s vcpu=%s mem=%s pid=%s" % (
            v.index, v.name, v.state, v.vcpu, v.mem_human, v.pid or "-"))

    print("== resolve by index / name / prefix ==")
    for sel in ("1", inv[0].name, inv[0].name[:4]):
        vm, e = vms.resolve(inv, sel)
        print("  %-20r -> %s" % (sel, vm.name if vm else "ERR:" + e))

    print("== action registry ==")
    for a in actions.all_actions():
        print("  %-8s destructive=%s applies=%s" % (a.name, a.destructive, a.applies_to))
    if actions.load_errors:
        print("  LOAD ERRORS:", actions.load_errors)

    session.logout(s)
    print("== done (no VM state changed) ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
