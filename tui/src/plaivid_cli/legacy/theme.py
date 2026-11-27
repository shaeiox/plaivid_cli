"""Terminal styling - colors, glyphs and rounded borders.

Palette and glyph set follow the gemini-cli TUI design system (256-color ANSI
with graceful fallback). Everything degrades to plain text when the output is
not a TTY or NO_COLOR is set, so piping the app never produces escape soup.
"""

import os
import sys

_enabled = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None

# --- 256-color palette (role -> ANSI 256 index) ------------------------------
FG = 253          # foreground / default text
PRIMARY = 111     # primary accent (headings, running)
SECONDARY = 183   # brand / subsections
ACCENT = 116      # info, values, paths, inline code
SUCCESS = 194     # success / started
WARNING = 229     # caution / pending / confirm
ERROR = 211       # errors / off
MUTED = 244       # borders, dim text, hints
SURFACE = 236     # block backgrounds


def _wrap(code):
    def f(text):
        if not _enabled:
            return str(text)
        return "\033[38;5;%dm%s\033[0m" % (code, text)
    return f


fg = _wrap(FG)
primary = _wrap(PRIMARY)
secondary = _wrap(SECONDARY)
accent = _wrap(ACCENT)
success = _wrap(SUCCESS)
warning = _wrap(WARNING)
error = _wrap(ERROR)
muted = _wrap(MUTED)


def bold(text):
    return ("\033[1m%s\033[0m" % text) if _enabled else str(text)


def color(text, code):
    return _wrap(code)(text)


# --- glyphs (unicode with ASCII fallback) ------------------------------------
_unicode = _enabled and os.environ.get("PLAIVID_ASCII") is None

_GLYPHS = {
    "ok": ("✓", "+"),
    "err": ("✗", "x"),
    "run": ("●", "*"),
    "ask": ("?", "?"),
    "pending": ("○", "o"),
    "cancel": ("-", "-"),
    "dot": ("•", "*"),
    "arrow": ("❯", ">"),
}


def glyph(name):
    u, a = _GLYPHS.get(name, ("?", "?"))
    return u if _unicode else a


# --- rounded box-drawing parts -----------------------------------------------
if _unicode:
    BOX = {"tl": "╭", "tr": "╮", "bl": "╰", "br": "╯",
           "h": "─", "v": "│"}
else:
    BOX = {"tl": "+", "tr": "+", "bl": "+", "br": "+", "h": "-", "v": "|"}


# --- state -> (color fn, glyph) ----------------------------------------------
def state_style(state):
    s = (state or "").lower()
    if s in ("started", "running"):
        return success, glyph("run")
    if s == "stopped":
        return muted, glyph("cancel")
    if s == "off":
        return error, glyph("err")
    return warning, glyph("pending")
