"""The orchestrator - the only component that knows about all the others.

It owns the session, the data refresh, the screen, and command dispatch, but
it delegates every real operation to an independent module (transport,
session, vms, monitoring, render, and each action file). If any one of those
raises, the orchestrator catches it, shows a message, and keeps running.
"""

import getpass
import os
import sys
import time

try:
    import readline  # line editing + Tab completion (POSIX; absent on Windows)
except ImportError:
    readline = None

from . import actions, config, monitoring, render, session, theme, transport, vms


class Context(object):
    """Minimal context handed to action modules."""

    def __init__(self, session_obj):
        self.session = session_obj

    @property
    def token(self):
        return self.session.token if self.session else None


BUILTINS_HELP = [
    ("list | ls | refresh", "reload the VM list and host status"),
    ("overview | mon", "live monitoring: CPU, load, memory, network, storage"),
    ("status", "refresh and show host monitoring"),
    ("<action> <id|name>", "run an action, e.g. 'stop 3' or 'start Hadi-New'"),
    ("help | ?", "show this help"),
    ("logout", "clear the saved session and exit"),
    ("quit | q", "exit (keeps the session cached)"),
]


class App(object):
    def __init__(self):
        self.session = None
        self.ctx = None
        self.vms = []
        self.host = {}
        self.status = ""

    # --- session ------------------------------------------------------------
    def _prompt_credentials(self):
        print(render.frame("Sign in", [
            render.info("No active session - please log in."),
            render.hint("Host: %s" % (self.host.get("name") or "PVM")),
        ], theme.warning))
        user = input(theme.accent("  Username [%s]: " % config.DEFAULT_USER)).strip()
        user = user or config.DEFAULT_USER
        password = getpass.getpass(theme.accent("  Password: "))
        return user, password

    def ensure_session(self):
        try:
            self.session, fresh = session.resume_or_prompt(self._prompt_credentials)
        except transport.TransportError as exc:
            print(render.err("Login failed: %s" % exc))
            return False
        self.ctx = Context(self.session)
        if fresh:
            print(render.ok("Logged in as %s" % theme.accent(self.session.username)))
        return True

    # --- data ---------------------------------------------------------------
    def refresh(self):
        try:
            self.host = monitoring.host_status(self.ctx.token)
        except transport.TransportError as exc:
            self.host = {"error": str(exc)}
        try:
            self.vms = vms.inventory(self.ctx.token)
        except transport.TransportError as exc:
            self.vms = []
            self.status = render.err("Could not list VMs: %s" % exc)

    # --- screen -------------------------------------------------------------
    def _clear(self):
        if sys.stdout.isatty():
            sys.stdout.write("\033[2J\033[H")

    def draw(self):
        self._clear()
        print(render.center(render.banner()))
        print(render.center(render.host_panel(self.host)))
        print(render.center(render.vm_table(self.vms)))
        if self.status:
            print()
            print(render.center(self.status))
        print()
        print(render.center(render.hint(
            "actions: %s   %s   Tab completes   %s   help   %s   quit" % (
                ", ".join(a.name for a in actions.all_actions()),
                theme.glyph("dot"), theme.glyph("dot"), theme.glyph("dot")))))

    # --- dispatch -----------------------------------------------------------
    def dispatch(self, line):
        """Handle one command line. Returns False to exit."""
        parts = line.split()
        if not parts:
            return True
        cmd = parts[0].lower()
        rest = " ".join(parts[1:])

        if cmd in ("quit", "q", "exit"):
            return False
        if cmd in ("help", "?", "h"):
            self.status = self._help_text()
            return True
        if cmd in ("list", "ls", "l", "refresh", "r", "status", "s"):
            self.refresh()
            self.status = render.ok("Refreshed")
            return True
        if cmd in ("overview", "mon", "monitor", "live"):
            self._overview()
            return True
        if cmd == "logout":
            session.logout(self.session)
            print(render.ok("Session cleared."))
            return False

        action = actions.get(cmd)
        if action is None:
            self.status = render.err("Unknown command '%s' (try: help)" % cmd)
            return True
        self._run_action(action, rest)
        return True

    def _run_action(self, action, selector):
        vm, errmsg = vms.resolve(self.vms, selector)
        if vm is None:
            self.status = render.err(errmsg)
            return
        if action.destructive and not self._confirm(action, vm):
            self.status = render.hint("%s cancelled." % action.label)
            return
        try:
            result = action.run(self.ctx, vm)
        except Exception as exc:  # an action bug must not crash the app
            self.status = render.err("%s failed: %s: %s"
                                     % (action.label, type(exc).__name__, exc))
            return
        label = "%s %s" % (action.label, theme.accent(vm.name))
        self.status = (render.ok("%s - %s" % (label, result.message))
                       if result.ok else
                       render.err("%s - %s" % (label, result.message)))
        self.refresh()

    def _confirm(self, action, vm):
        if not sys.stdin.isatty():
            return True  # non-interactive: assume intent
        print(render.frame("Confirm", [
            render.warn("%s  %s  (%s)" % (
                theme.bold(action.label.upper()),
                theme.accent(vm.name), vm.uuid[:8])),
            render.hint(action.description),
        ], theme.warning))
        try:
            ans = input(theme.warning("  Proceed? [y/N]: ")).strip().lower()
        except EOFError:
            return False
        return ans in ("y", "yes")

    def _help_text(self):
        lines = [theme.bold("Commands")]
        for name, desc in BUILTINS_HELP:
            lines.append("  %s  %s" % (theme.accent(render_ljust(name, 22)),
                                       theme.muted(desc)))
        lines.append("")
        lines.append(theme.bold("VM actions") + theme.muted("  (by id number or name)"))
        for a in actions.all_actions():
            mark = theme.warning(" !") if a.destructive else "  "
            lines.append("  %s%s %s" % (
                theme.accent(render_ljust(a.name, 10)), mark,
                theme.muted(a.description)))
        if actions.load_errors:
            lines.append("")
            lines.append(theme.error("Disabled actions (failed to load):"))
            for name, e in actions.load_errors.items():
                lines.append("  " + theme.error("%s - %s" % (name, e)))
        return "\n".join(lines)

    # --- input: line editing + Tab completion -------------------------------
    def _setup_readline(self):
        if readline is None:
            return
        try:
            # only whitespace splits words, so hyphens in VM names survive
            readline.set_completer_delims(" \t\n")
            readline.set_completer(self._complete)
            for binding in (
                "tab: complete",
                "set show-all-if-ambiguous on",    # list candidates on 1st Tab
                "set show-all-if-unmodified on",
                "set completion-ignore-case on",
                "set colored-completion-prefix on",
            ):
                readline.parse_and_bind(binding)
            if hasattr(readline, "set_completion_display_matches_hook"):
                readline.set_completion_display_matches_hook(self._display_matches)
        except Exception:
            pass

    def _display_matches(self, substitution, matches, longest):
        """Render the Tab candidate list as a themed, columnar menu."""
        try:
            cols = render.term_width()
            cell = max(longest + 2, 10)
            per = max(1, cols // cell)
            sys.stdout.write("\n")
            line = ""
            for i, m in enumerate(matches):
                line += m.ljust(cell)
                if (i + 1) % per == 0:
                    sys.stdout.write(theme.accent(line.rstrip()) + "\n")
                    line = ""
            if line.strip():
                sys.stdout.write(theme.accent(line.rstrip()) + "\n")
            sys.stdout.write(self._echo_prompt() + readline.get_line_buffer())
            sys.stdout.flush()
        except Exception:
            pass

    def _command_vocab(self):
        vocab = ["list", "status", "refresh", "overview", "help", "logout", "quit"]
        for a in actions.all_actions():
            vocab.append(a.name)
            vocab.extend(a.aliases)
        return vocab

    def _selector_vocab(self):
        vocab = []
        for vm in self.vms:
            vocab.append(str(vm.index))
            vocab.append(vm.name)
        return vocab

    def _complete(self, text, state):
        if readline is None:
            return None
        try:
            preceding = readline.get_line_buffer()[:readline.get_begidx()].split()
            vocab = self._command_vocab() if not preceding else self._selector_vocab()
            tl = text.lower()
            cands = sorted(set(v for v in vocab if v.lower().startswith(tl)))
            return cands[state] if state < len(cands) else None
        except Exception:
            return None

    def _prompt(self):
        pad = " " * render.margin()
        if readline is not None and theme._enabled:
            # wrap color codes in \001..\002 so readline counts width correctly
            return ("%s\001\033[1;38;5;%dm\002%s \001\033[0m\002"
                    % (pad, theme.PRIMARY, theme.glyph("arrow")))
        return "%s%s " % (pad, theme.glyph("arrow"))

    def _echo_prompt(self):
        """Prompt with real escapes (no readline \\001\\002) for manual echo."""
        pad = " " * render.margin()
        if theme._enabled:
            return "%s\033[1;38;5;%dm%s \033[0m" % (pad, theme.PRIMARY,
                                                    theme.glyph("arrow"))
        return "%s%s " % (pad, theme.glyph("arrow"))

    # --- live overview ------------------------------------------------------
    _SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def _overview(self):
        """Live monitoring page: refresh until the user presses q / Ctrl-C."""
        try:
            interval = max(1.0, float(os.environ.get("PLAIVID_REFRESH", "3")))
        except ValueError:
            interval = 3.0
        try:
            tapmap = vms.tap_map(self.ctx.token)
        except transport.TransportError:
            tapmap = {}
        frames = self._SPIN if theme._unicode else "|/-\\"
        prev = None
        tick = 0
        try:
            while True:
                snap = monitoring.metrics_snapshot(self.ctx.token)
                try:
                    self.vms = vms.inventory(self.ctx.token)
                except transport.TransportError:
                    pass
                agg = vms.aggregate(self.vms)
                spin = theme.primary(frames[tick % len(frames)])
                self._clear()
                print(render.center(render.overview(
                    snap, prev, tapmap, agg, spin)))
                print()
                print(render.center(render.hint(
                    "live monitoring  %s  refresh %gs  %s  q / Ctrl-C to exit"
                    % (theme.glyph("dot"), interval, theme.glyph("dot")))))
                tick += 1
                if not sys.stdin.isatty():
                    if prev is not None:
                        break          # one-shot: second pass shows rates
                    prev = snap
                    time.sleep(1.0)
                    continue
                prev = snap
                if not self._wait_or_quit(interval):
                    break
        except KeyboardInterrupt:
            pass
        self.status = render.hint("Exited live monitoring.")

    def _wait_or_quit(self, interval):
        """Sleep up to ``interval``; return False if the user asked to quit."""
        if not sys.stdin.isatty():
            return False
        try:
            import select
            import termios
            import tty
        except ImportError:
            time.sleep(interval)
            return True
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            ready, _, _ = select.select([sys.stdin], [], [], interval)
            if ready:
                ch = sys.stdin.read(1)
                if ch.lower() == "q" or ch == "\x03":
                    return False
        except Exception:
            time.sleep(interval)
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
            except Exception:
                pass
        return True

    # --- entry points -------------------------------------------------------
    def run_interactive(self):
        if not self.ensure_session():
            return 1
        self._setup_readline()
        self.refresh()
        while True:
            self.draw()
            try:
                print()
                line = input(self._prompt())
            except (EOFError, KeyboardInterrupt):
                print()
                break
            try:
                if not self.dispatch(line):
                    break
            except Exception as exc:  # last-resort guard for the loop
                self.status = render.err("Error: %s: %s" % (type(exc).__name__, exc))
        return 0

    def run_once(self, args):
        if not self.ensure_session():
            return 1
        self.refresh()
        line = " ".join(args)
        cmd = args[0].lower()
        if cmd in ("list", "ls", "status", "s"):
            self.draw()
            return 0
        if cmd in ("overview", "mon", "monitor", "live"):
            self._overview()
            return 0
        self.dispatch(line)
        # print just the resulting status line for scripting
        print(self.status or render.ok("done"))
        return 0


def render_ljust(s, n):
    return s + " " * max(0, n - len(s))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    app = App()
    try:
        if argv:
            return app.run_once(argv)
        return app.run_interactive()
    except transport.TransportError as exc:
        print(render.err(str(exc)))
        return 1
