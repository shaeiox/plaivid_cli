"""Small ANSI terminal renderer with line-level diffing.

The layout is composed by ``render``; this class owns only the output buffer.
It writes changed rows at absolute coordinates and never scrolls the terminal
while the full-screen TUI is active.
"""

import re

_ANSI = re.compile(r"\033\[[0-?]*[ -/]*[@-~]")


class TerminalRenderer(object):
    """Double-buffer terminal rows and emit only changed lines."""

    def __init__(self, stream):
        self.stream = stream
        self.previous = None
        self.dimensions = None

    @staticmethod
    def _clip(line, width):
        """Clip a colored line to terminal columns without counting escapes."""
        out = []
        visible = 0
        pos = 0
        for match in _ANSI.finditer(line):
            text = line[pos:match.start()]
            for char in text:
                if visible >= width:
                    break
                out.append(char)
                visible += 1
            if visible >= width:
                break
            out.append(match.group(0))
            pos = match.end()
        if visible < width:
            for char in line[pos:]:
                if _ANSI.match(line, pos):
                    match = _ANSI.match(line, pos)
                    out.append(match.group(0))
                    pos = match.end()
                    continue
                if visible >= width:
                    break
                out.append(char)
                visible += 1
                pos += 1
        if visible >= width and "\033[" in line:
            out.append("\033[0m")
        return "".join(out)

    def paint(self, lines, width, height):
        """Draw a frame, clearing once on first paint or terminal resize."""
        width = max(1, int(width))
        height = max(1, int(height))
        dimensions = (width, height)
        frame = [self._clip(line, width) for line in list(lines)[:height]]
        output = []
        if self.dimensions != dimensions or self.previous is None:
            output.append("\033[2J")
            self.previous = []
            self.dimensions = dimensions

        old = self.previous
        max_rows = max(len(old), len(frame))
        for row in range(max_rows):
            current = frame[row] if row < len(frame) else ""
            prior = old[row] if row < len(old) else None
            if current != prior:
                output.append("\033[%d;1H%s\033[K" % (row + 1, current))
        # Clear only the command-prompt row below the frame; never erase or
        # scroll the static dashboard zones during a list update.
        if len(frame) < height:
            output.append("\033[%d;1H\033[2K" % (len(frame) + 1))
        if output:
            self.stream.write("".join(output))
            self.stream.flush()
        self.previous = frame

    def invalidate(self):
        """Force a complete paint on the next frame."""
        self.previous = None
        self.dimensions = None
