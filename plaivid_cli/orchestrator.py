"""The orchestrator - the only component that knows about all the others.

It owns the session, the data refresh, the screen, and command dispatch, but
it delegates every real operation to an independent module (transport,
session, vms, monitoring, render, and each action file). If any one of those
raises, the orchestrator catches it, shows a message, and keeps running.
"""

import getpass
import sys
import time

try:
    import readline  # line editing + Tab completion (POSIX; absent on Windows)
except ImportError:
    readline = None

from . import (actions, commands, config, monitoring, render, session, theme,
               transport, vms)
from .version import __version__


class Context(object):
    """Minimal context handed to action modules."""

    def __init__(self, session_obj):
        self.session = session_obj

    @property
    def token(self):
        return self.session.token if self.session else None


class App(object):
    def __init__(self):
        self.session = None
        self.ctx = None
        self.vms = []
        self.host = {}
        self.status = ""
        self.cmd_ctx = commands.CommandContext(self)

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
        dot = theme.glyph("dot")
        print(render.center(render.hint(
            "actions: %s   %s   Tab completes   %s   help   %s   quit   %s   %s" % (
                ", ".join(a.name for a in actions.all_actions()),
                dot, dot, dot, dot,
                theme.secondary("Plaivid CLI v" + __version__)))))

    # --- dispatch -----------------------------------------------------------
    def dispatch(self, line):
        """Handle one command line. Returns False to exit.

        Registry-first: a command from the ``commands/`` registry, then an
        action from the ``actions/`` registry (the ``<action> <targets>``
        form), else unknown. Nothing here is hard-coded per verb, so adding a
        file to either package is all it takes to add behavior.
        """
        parts = line.split()
        if not parts:
            return True
        cmd = parts[0].lower()
        rest = " ".join(parts[1:])
        self.cmd_ctx.reset()

        command = commands.get(cmd)
        if command is not None:
            return command.run(self.cmd_ctx, rest) != commands.EXIT

        action = actions.get(cmd)
        if action is not None:
            self._run_action(action, rest)
            return True

        self.status = render.err("Unknown command '%s' (try: help)" % cmd)
        return True

    def _run_action(self, action, selector):
        targets, errmsg = vms.resolve_many(self.vms, selector)
        if not targets:
            self.status = render.err(errmsg or "no VM matched")
            return
        if action.destructive and not self._confirm(action, targets):
            self.status = render.hint("%s cancelled." % action.label)
            return
        if len(targets) == 1:
            self.status = self._apply_one(action, targets[0])
        else:
            self.status = self._apply_bulk(action, targets)
        self.refresh()

    def _apply_one(self, action, vm):
        try:
            result = action.run(self.ctx, vm)
        except Exception as exc:  # an action bug must not crash the app
            return render.err("%s %s failed: %s: %s"
                              % (action.label, vm.name, type(exc).__name__, exc))
        label = "%s %s" % (action.label, theme.accent(vm.name))
        return (render.ok("%s - %s" % (label, result.message)) if result.ok
                else render.err("%s - %s" % (label, result.message)))

    def _apply_bulk(self, action, targets):
        ok = fail = 0
        failed = []
        for vm in targets:
            try:
                result = action.run(self.ctx, vm)
                good = result.ok
            except Exception:
                good = False
            if good:
                ok += 1
            else:
                fail += 1
                failed.append(vm.name)
        msg = "%s on %d VMs: %s ok" % (action.label, len(targets),
                                       theme.success(str(ok)))
        if fail:
            msg += ", %s failed (%s)" % (theme.error(str(fail)),
                                         ", ".join(failed[:5]))
        return (render.ok(msg) if not fail else render.warn(msg))

    def _confirm(self, action, targets):
        if not sys.stdin.isatty():
            return True  # non-interactive: assume intent
        if len(targets) == 1:
            body = [render.warn("%s  %s  (%s)" % (
                theme.bold(action.label.upper()),
                theme.accent(targets[0].name), targets[0].uuid[:8])),
                render.hint(action.description)]
        else:
            names = ", ".join(vm.name for vm in targets[:8])
            if len(targets) > 8:
                names += ", +%d more" % (len(targets) - 8)
            body = [render.warn("%s  %s VMs" % (
                theme.bold(action.label.upper()), theme.accent(str(len(targets))))),
                render.hint(names)]
        print(render.frame("Confirm", body, theme.warning))
        try:
            ans = input(theme.warning("  Proceed? [y/N]: ")).strip().lower()
        except EOFError:
            return False
        return ans in ("y", "yes")

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
        vocab = []
        for c in commands.all_commands():
            vocab.append(c.name)
            vocab.extend(c.aliases)
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

    # --- live-page helpers (used by page commands like overview) ------------
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

    def _page(self, body, note):
        """Clear, print a page, wait for Enter on a TTY, set a status note."""
        self._clear()
        print(render.center(body))
        if sys.stdin.isatty():
            try:
                input("\n" + " " * render.margin()
                      + theme.muted("press Enter to return "))
            except (EOFError, KeyboardInterrupt):
                print()
        self.status = render.hint(note)

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
        self.dispatch(" ".join(args))
        # A page command already drew itself; a dashboard command asked for a
        # redraw; anything else leaves just a status line to print.
        if self.cmd_ctx.redraw:
            self.draw()
        elif not self.cmd_ctx.rendered:
            print(self.status or render.ok("done"))
        return 0


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
