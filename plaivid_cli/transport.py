"""Low-level transport: run sbell / pvm-running-vms and parse the XML envelope.

This is the only module that shells out. Everything above it works with the
``Response`` object and never touches subprocess or raw XML, so the transport
could later be swapped (SSH, the sabad HTTP API, a native socket client)
without changing any caller.
"""

import subprocess
import xml.etree.ElementTree as ET

from . import config

# Human-readable meanings for the common sballd error numbers.
ERRNO_HINT = {
    "39": "Unauthorized - session missing or expired (log in again).",
    "40": "Permission denied - often a malformed params body, not a real "
          "rights problem.",
    "106": "Bad module name.",
    "107": "Bad command name.",
    "108": "Socket permission denied - sbell must run as root (use sudo).",
    "137": "Username or password is not correct.",
    "146": "VM state error (e.g. the VM is already running / already off).",
}


class TransportError(Exception):
    """A command could not be run or its output could not be parsed."""


class Response(object):
    """A parsed ``<response>`` envelope from sballd."""

    def __init__(self, raw, status, action_id, description, errno, what, mid):
        self.raw = raw
        self.status = status
        self.action_id = action_id
        self.description = description      # ElementTree element, or None
        self.errno = errno
        self.what = what
        self.mid = mid

    @property
    def ok(self):
        return self.status == "success"

    @property
    def token(self):
        """For user/login the token is the description's text."""
        if self.description is not None and self.description.text:
            return self.description.text.strip()
        return None

    def error_text(self):
        parts = []
        if self.what:
            parts.append(self.what)
        if self.errno:
            hint = ERRNO_HINT.get(self.errno)
            parts.append("[errno %s]" % self.errno)
            if hint:
                parts.append(hint)
        return " ".join(parts) or "unknown error"


def _run(argv, timeout=None):
    try:
        p = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL, universal_newlines=True)
        out, err = p.communicate(timeout=timeout or config.CMD_TIMEOUT)
    except subprocess.TimeoutExpired:
        p.kill()
        raise TransportError("command timed out: %s" % " ".join(argv[:3]))
    except OSError as exc:
        raise TransportError("cannot run %r: %s" % (argv[0], exc))
    return p.returncode, out, err


def _parse_envelope(raw):
    text = (raw or "").strip()
    if not text.startswith("<"):
        raise TransportError("unexpected output: %s" % text[:200])
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise TransportError("could not parse response: %s" % exc)
    status = root.findtext("status") or ""
    action_id = root.findtext("action_id") or ""
    desc = root.find("description")
    errno = what = mid = None
    if desc is not None:
        errno = desc.findtext("errno")
        what = desc.findtext("what")
        mid = desc.findtext("mid")
    return Response(text, status, action_id, desc, errno, what, mid)


def systemd_property(unit, prop, timeout=2):
    """Read one systemd property without making service checks fatal.

    Returns ``None`` on non-systemd hosts, missing units, or command failure.
    Kept in this module so process execution remains isolated here.
    """
    try:
        rc, out, _err = _run(["systemctl", "show", unit,
                              "-p", prop, "--value"], timeout)
    except TransportError:
        return None
    value = (out or "").strip()
    return value if rc == 0 and value and value != "n/a" else None


def sbell(module, command, params="<params/>", token=None, timeout=None):
    """Run ``sbell <module> <command> <params> [token]`` and parse the reply."""
    argv = list(config.SBELL_CMD) + [module, command, params]
    if token:
        argv.append(token)
    rc, out, err = _run(argv, timeout)
    if not out.strip() and err.strip():
        raise TransportError(err.strip().splitlines()[-1])
    return _parse_envelope(out)


def running_vms_raw(timeout=None):
    """Run pvm-running-vms and return its raw stdout."""
    rc, out, err = _run(config.RUNNING_VMS_CMD, timeout)
    if rc != 0 and not out.strip():
        raise TransportError((err or "pvm-running-vms failed").strip())
    return out
