"""Static configuration and paths.

Everything that another module might want to tweak lives here so the rest of
the code has no magic constants scattered through it. Values can be overridden
with environment variables, which keeps the tool portable between hosts.
"""

import os
import shlex

# --- transport commands ------------------------------------------------------
# sbell needs root (its sballd socket is root-only), so by default we prefix it
# with sudo. Override with PLAIVID_SBELL, e.g. "sbell" when already root.
SBELL_CMD = shlex.split(os.environ.get("PLAIVID_SBELL", "sudo sbell"))

# pvm-running-vms is read-only and works without root.
RUNNING_VMS_CMD = shlex.split(os.environ.get("PLAIVID_RUNNING_VMS", "pvm-running-vms"))

# How long (seconds) to wait for any single sbell/pvm command.
CMD_TIMEOUT = int(os.environ.get("PLAIVID_CMD_TIMEOUT", "30"))

# --- session cache -----------------------------------------------------------
# Where the login token is cached so reopening the TUI does not re-prompt.
_default_state = os.path.join(
    os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")),
    "plaivid",
)
STATE_DIR = os.environ.get("PLAIVID_STATE_DIR", _default_state)
SESSION_FILE = os.path.join(STATE_DIR, "session.json")

# Product context sent to the API layer (sbell ignores it, kept for parity).
PRODUCT = os.environ.get("PLAIVID_PRODUCT", "Plaivid")

# Default username offered at the login prompt (never a password).
DEFAULT_USER = os.environ.get("PLAIVID_USER", "manage")
