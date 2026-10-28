"""The orchestrator - the only component that knows about all the others.

It owns the session, the data refresh, the screen, and command dispatch, but
it delegates every real operation to an independent module (transport,
session, vms, monitoring, render, and each action file). If any one of those
raises, the orchestrator catches it, shows a message, and keeps running.
"""

import codecs
import getpass
import os
import shutil
import sys
import time

try:
    import readline  # line editing + Tab completion (POSIX; absent on Windows)
except ImportError:
    readline = None

from . import (actions, commands, config, monitoring, render, session, theme,
               transport, vms)
from .terminal import TerminalRenderer
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
        self.sort_key = None      # VM-list order, set by the `sort` command
        self.sort_desc = False
        self.scroll_offset = 0      # first VM row in the visible list window
        self.vm_limit = 0
        self._screen = None
        self._terminal_size = None
        self._layout_key = None
        self._layout_compact = False
        self._layout_ultra_compact = False
        self._history = []
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
            self.vms = vms.sort_vms(vms.inventory(self.ctx.token),
                                    self.sort_key, self.sort_desc)
        except transport.TransportError as exc:
            self.vms = []
            self.status = render.err("Could not list VMs: %s" % exc)

    # --- screen -------------------------------------------------------------
    def _enter_fullscreen(self):
        """Take over the terminal screen until the interactive session exits."""
        if sys.stdin.isatty() and sys.stdout.isatty():
            # Use SGR mouse reporting so wheel events arrive as complete CSI
            # sequences and can be consumed before command-line text handling.
            sys.stdout.write("\033[?1049h\033[?25l\033[?1000h\033[?1006h\033[H")
            sys.stdout.flush()
            self._fullscreen = True
            self._screen = TerminalRenderer(sys.stdout)

    def _leave_fullscreen(self):
        """Restore the shell screen and cursor on every exit path."""
        if getattr(self, "_fullscreen", False):
            sys.stdout.write("\033[?1006l\033[?1000l\033[?25h\033[?1049l")
            sys.stdout.flush()
            self._fullscreen = False

    def draw(self):
        sort_label = None
        if self.sort_key:
            sort_label = "%s %s" % (self.sort_key,
                                    "↓" if self.sort_desc else "↑")
        is_tty = sys.stdin.isatty() and sys.stdout.isatty()
        if not is_tty:
            print(render.center(render.dashboard(
                self.host, self.vms, sort_label, self.status)))
            return

        size = shutil.get_terminal_size((100, 24))
        rows, columns = size.lines, size.columns
        self._terminal_size = (columns, rows)
        sort_label = sort_label or ""
        vm_signature = tuple((vm.name, vm.uuid, vm.state, vm.vcpu, vm.mem_human,
                              vm.uptime, vm.pid, vm.port) for vm in self.vms)
        host_signature = tuple(sorted((key, str(value))
                                      for key, value in self.host.items()))
        layout_key = (rows, columns, sort_label, len(self.status),
                      host_signature, vm_signature)
        if layout_key != self._layout_key:
            compact = rows <= 40
            if not compact:
                full_base = render.dashboard(
                    self.host, self.vms, sort_label or None, self.status,
                    compact=False, vm_offset=0, vm_limit=0).splitlines()
                full_row_height = render.vm_row_height(columns, False, self.vms)
                # Switch to compact chrome if the full layout would leave fewer
                # than four VM rows visible; this reduces paging on short screens.
                if rows - 1 - len(full_base) < 4 * full_row_height:
                    compact = True
            ultra_compact = rows <= 18
            baseline = render.dashboard(
                self.host, self.vms, sort_label or None, self.status,
                compact=compact, ultra_compact=ultra_compact,
                vm_offset=0, vm_limit=0).splitlines()
            row_height = render.vm_row_height(columns, compact, self.vms)
            if self.vms:
                self.vm_limit = min(
                    len(self.vms), max(1, (rows - 1 - len(baseline)) // row_height))
                self.scroll_offset = min(
                    max(0, self.scroll_offset),
                    max(0, len(self.vms) - self.vm_limit))
            else:
                self.vm_limit = 0
                self.scroll_offset = 0
            self._layout_key = layout_key
            self._layout_compact = compact
            self._layout_ultra_compact = ultra_compact
        compact = self._layout_compact
        ultra_compact = self._layout_ultra_compact
        if self.vms:
            self.scroll_offset = min(
                max(0, self.scroll_offset),
                max(0, len(self.vms) - self.vm_limit))
        dashboard = render.dashboard(
            self.host, self.vms, sort_label, self.status, compact=compact,
            ultra_compact=ultra_compact, vm_offset=self.scroll_offset,
            vm_limit=self.vm_limit)
        lines = render.center(dashboard).splitlines()
        if len(lines) > rows - 1:
            # The terminal is too short for fixed chrome plus even one VM; keep
            # the top/static layout stable and let the minimum list region show.
            lines = lines[:rows - 1]
        if self._screen is None:
            self._screen = TerminalRenderer(sys.stdout)
        self._screen.paint(lines, columns, rows)

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
            if not preceding:
                vocab = self._command_vocab()
            else:
                # a command may declare its own argument words (e.g. sort fields)
                cmd = commands.get(preceding[0])
                vocab = cmd.complete if (cmd and cmd.complete) else self._selector_vocab()
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

    def _complete_buffer(self, buffer):
        """Simple prefix completion for the built-in raw terminal editor."""
        parts = buffer.split()
        if not parts:
            token = ""
            vocab = self._command_vocab()
        elif len(parts) == 1 and not buffer.endswith(" "):
            token = parts[0]
            vocab = self._command_vocab()
        else:
            token = "" if buffer.endswith(" ") else parts[-1]
            command = commands.get(parts[0])
            vocab = (command.complete if command and command.complete
                     else self._selector_vocab())
        matches = sorted(set(value for value in vocab
                             if value.lower().startswith(token.lower())))
        if not matches:
            return buffer
        prefix = matches[0]
        for candidate in matches[1:]:
            common = 0
            while common < min(len(prefix), len(candidate)) and \
                    prefix[common].lower() == candidate[common].lower():
                common += 1
            prefix = prefix[:common]
        if len(parts) <= 1 and not buffer.endswith(" "):
            return prefix
        if buffer.endswith(" "):
            return buffer + prefix
        return buffer[:-len(token)] + prefix if token else buffer + prefix

    def _scroll_vms(self, delta):
        """Move only the VM list window; static dashboard zones stay pinned."""
        maximum = max(0, len(self.vms) - max(1, self.vm_limit))
        self.scroll_offset = max(0, min(maximum, self.scroll_offset + delta))

    def _scroll_page(self, direction):
        """Move one visible-list page, not the entire screen viewport."""
        self._scroll_vms(direction * max(1, self.vm_limit))

    def _read_escape_sequence(self, select_fn, fd, csi_started=False):
        """Consume complete CSI/SS3 input directly from the fd, not TextIO.

        Reading ``sys.stdin`` one character at a time can pre-buffer the rest
        of an escape sequence; ``select`` then sees an empty fd and the buffered
        printable tail leaks into the prompt. ``os.read`` avoids that mismatch.
        """
        def read_after(timeout):
            ready, _, _ = select_fn([fd], [], [], timeout)
            return os.read(fd, 1) if ready else b""

        if csi_started:
            first = b"["
        else:
            first = read_after(0.25)
        if first == b"O":               # SS3 cursor keys: ESC O A/B
            return "O" + (read_after(0.25).decode("ascii", "ignore"))
        if first != b"[":
            return ""                   # consume unsupported escape prefix
        sequence = "["
        # CSI parameters/intermediates continue until a final byte (0x40-0x7e).
        for _ in range(64):
            raw = read_after(0.25)
            if not raw:
                break
            char = raw.decode("latin-1")
            sequence += char
            if "@" <= char <= "~":
                break
        return sequence

    def _read_mouse_scroll(self, sequence, select_fn, fd):
        """Return -1/+1 for wheel up/down, while consuming all mouse events."""
        if sequence.startswith("[<") and sequence[-1:] in ("M", "m"):
            try:
                button = int(sequence[2:-1].split(";", 1)[0])
            except (ValueError, IndexError):
                return 0
            if button & 64:
                return -1 if button & 1 == 0 else 1
            return 0
        if sequence == "[M":             # consume legacy X10's 3-byte payload
            payload = bytearray()
            for _ in range(3):
                ready, _, _ = select_fn([fd], [], [], 0.20)
                if not ready:
                    break
                payload.extend(os.read(fd, 1))
            if len(payload) == 3:
                button = payload[0] - 32
                if button & 64:
                    return -1 if button & 1 == 0 else 1
        return 0

    def _read_command(self):
        """Read a command while allowing PageUp/PageDown to scroll the screen."""
        if not sys.stdin.isatty():
            return input(self._prompt())
        try:
            import select
            import termios
            import tty
        except ImportError:
            return input(self._prompt())

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        buffer = ""
        history_pos = len(self._history)
        prompt = self._prompt()
        try:
            tty.setraw(fd)
            sys.stdout.write(prompt)
            sys.stdout.flush()
            decoder = codecs.getincrementaldecoder("utf-8")("replace")
            while True:
                ready, _, _ = select.select([fd], [], [], 0.25)
                if not ready:
                    size = shutil.get_terminal_size((100, 24))
                    if self._terminal_size != (size.columns, size.lines):
                        self.draw()
                        sys.stdout.write(prompt + buffer)
                        sys.stdout.flush()
                    continue
                raw = os.read(fd, 1)
                if not raw:
                    return None
                sequence = None
                if raw == b"\x1b":
                    sequence = self._read_escape_sequence(select.select, fd)
                elif raw == b"\x9b":          # 8-bit C1 CSI form
                    sequence = self._read_escape_sequence(
                        select.select, fd, csi_started=True)
                if sequence is not None:
                    wheel = self._read_mouse_scroll(sequence, select.select, fd)
                    if sequence in ("[5~", "[5;2~") or wheel < 0:
                        self._scroll_vms(-3 if wheel else -max(1, self.vm_limit))
                        self.draw()
                    elif sequence in ("[6~", "[6;2~") or wheel > 0:
                        self._scroll_vms(3 if wheel else max(1, self.vm_limit))
                        self.draw()
                    elif sequence in ("[A", "OA") and self._history:
                        history_pos = max(0, history_pos - 1)
                        buffer = self._history[history_pos]
                    elif sequence in ("[B", "OB") and self._history:
                        history_pos = min(len(self._history), history_pos + 1)
                        buffer = (self._history[history_pos]
                                  if history_pos < len(self._history) else "")
                    sys.stdout.write("\r\033[2K" + prompt + buffer)
                    sys.stdout.flush()
                    continue
                char = decoder.decode(raw)
                if not char:
                    continue
                if char in ("\r", "\n"):
                    sys.stdout.write("\r\n")
                    sys.stdout.flush()
                    if buffer.strip():
                        self._history.append(buffer)
                    self.scroll_offset = 0
                    return buffer
                if char == "\x03":
                    raise KeyboardInterrupt
                if char == "\x04":
                    return None if not buffer else buffer
                if char in ("\x7f", "\b"):
                    if buffer:
                        buffer = buffer[:-1]
                        sys.stdout.write("\b \b")
                        sys.stdout.flush()
                    continue
                if char == "\t":
                    buffer = self._complete_buffer(buffer)
                    sys.stdout.write("\r\033[2K" + prompt + buffer)
                    sys.stdout.flush()
                    continue
                if char.isprintable():
                    buffer += char
                    sys.stdout.write(char)
                    sys.stdout.flush()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    # --- entry points -------------------------------------------------------
    def run_interactive(self):
        self._enter_fullscreen()
        try:
            if not self.ensure_session():
                # Preserve login errors on the normal terminal screen.
                self._leave_fullscreen()
                return 1
            self._setup_readline()
            self.refresh()
            while True:
                self.draw()
                try:
                    line = self._read_command()
                    if line is None:
                        print()
                        break
                except (EOFError, KeyboardInterrupt):
                    print()
                    break
                try:
                    if not self.dispatch(line):
                        break
                except Exception as exc:  # last-resort guard for the loop
                    self.status = render.err(
                        "Error: %s: %s" % (type(exc).__name__, exc))
            return 0
        finally:
            self._leave_fullscreen()

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
        # No arguments launches the full-screen TUI by default. `tui` and
        # `--tui` are explicit equivalents for scripts/desktop launchers.
        if not argv or argv == ["tui"] or argv == ["--tui"]:
            return app.run_interactive()
        return app.run_once(argv)
    except transport.TransportError as exc:
        print(render.err(str(exc)))
        return 1
