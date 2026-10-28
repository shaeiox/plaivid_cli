"""Command registry with per-file error isolation.

Every ``*.py`` in this package (except base/__init__) is a candidate command,
imported independently. A file that fails to import or lacks the required
attributes is recorded in ``load_errors`` and skipped - the rest of the CLI
keeps working. This is what makes "add a file = add a command" true: dispatch,
Tab completion and help all read from here.
"""

import importlib
import os
import pkgutil

from .base import CommandContext, CONTINUE, EXIT  # noqa: F401 (re-exported)

_REQUIRED = ("NAME", "run")

_commands = {}      # name/alias -> _Command
_ordered = []       # unique commands, sorted
load_errors = {}    # module name -> error string


class _Command(object):
    def __init__(self, module):
        self.module = module
        self.name = module.NAME
        self.aliases = list(getattr(module, "ALIASES", []))
        self.description = getattr(module, "DESCRIPTION", "")
        self.usage = getattr(module, "USAGE", module.NAME)
        self.order = int(getattr(module, "ORDER", 100))
        self.complete = list(getattr(module, "COMPLETE", []))

    def run(self, ctx, args):
        return self.module.run(ctx, args)


def _discover():
    pkg_dir = os.path.dirname(__file__)
    for info in pkgutil.iter_modules([pkg_dir]):
        name = info.name
        if name in ("base",) or name.startswith("_"):
            continue
        try:
            mod = importlib.import_module("%s.%s" % (__name__, name))
            for attr in _REQUIRED:
                if not hasattr(mod, attr):
                    raise AttributeError("missing %s" % attr)
            command = _Command(mod)
        except Exception as exc:  # isolation: one bad command never blocks others
            load_errors[name] = "%s: %s" % (type(exc).__name__, exc)
            continue
        _ordered.append(command)
        _commands[command.name.lower()] = command
        for alias in command.aliases:
            _commands[alias.lower()] = command
    _ordered.sort(key=lambda c: (c.order, c.name))


def load():
    if not _ordered and not load_errors:
        _discover()
    return _ordered


def get(name):
    if not _ordered and not load_errors:
        _discover()
    return _commands.get((name or "").lower())


def all_commands():
    return list(load())
