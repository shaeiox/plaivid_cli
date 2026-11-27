"""Action registry with per-module error isolation.

Every ``*.py`` file in this package (other than base/__init__) is treated as a
candidate action and imported independently. If one fails to import or is
missing required attributes, it is skipped and recorded in ``load_errors`` -
the rest of the app keeps working. This is what lets individual actions be
added, updated or broken without taking the whole CLI down.
"""

import importlib
import os
import pkgutil

_REQUIRED = ("NAME", "LABEL", "run")

_actions = {}       # name/alias -> module
_ordered = []       # unique modules, sorted
load_errors = {}    # module name -> error string


class _Action(object):
    """Thin wrapper exposing an action module with safe defaults."""

    def __init__(self, module):
        self.module = module
        self.name = module.NAME
        self.aliases = list(getattr(module, "ALIASES", []))
        self.label = module.LABEL
        self.description = getattr(module, "DESCRIPTION", "")
        self.applies_to = set(getattr(module, "APPLIES_TO", set()))
        self.destructive = bool(getattr(module, "DESTRUCTIVE", False))
        self.order = int(getattr(module, "ORDER", 100))

    def applies(self, vm):
        if not self.applies_to:
            return True
        state = (vm.state if not vm.running else "started")
        return state in self.applies_to or (vm.running and
                                            "running" in self.applies_to)

    def run(self, ctx, vm):
        return self.module.run(ctx, vm)


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
            action = _Action(mod)
        except Exception as exc:  # isolation: one bad action never blocks others
            load_errors[name] = "%s: %s" % (type(exc).__name__, exc)
            continue
        _ordered.append(action)
        _actions[action.name.lower()] = action
        for alias in action.aliases:
            _actions[alias.lower()] = action
    _ordered.sort(key=lambda a: (a.order, a.name))


def load():
    if not _ordered and not load_errors:
        _discover()
    return _ordered


def get(name):
    if not _ordered and not load_errors:
        _discover()
    return _actions.get((name or "").lower())


def all_actions():
    return list(load())
