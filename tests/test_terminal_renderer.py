"""Regression tests for stable line-diff terminal painting."""

import io
import unittest

from plaivid_cli.terminal import TerminalRenderer


class TerminalRendererTests(unittest.TestCase):
    def test_only_changed_vm_rows_are_repainted(self):
        output = io.StringIO()
        screen = TerminalRenderer(output)
        screen.paint(["header", "vm row A", "vm row B", "footer"], 30, 10)
        output.seek(0)
        output.truncate(0)
        screen.paint(["header", "vm row X", "vm row B", "footer"], 30, 10)
        diff = output.getvalue()
        self.assertIn("\033[2;1Hvm row X", diff)
        self.assertNotIn("\033[1;1H", diff)
        self.assertNotIn("\033[3;1H", diff)
        self.assertNotIn("\033[4;1H", diff)

    def test_resize_invalidates_and_repaints_frame(self):
        output = io.StringIO()
        screen = TerminalRenderer(output)
        screen.paint(["stable"], 30, 10)
        output.seek(0)
        output.truncate(0)
        screen.paint(["stable"], 40, 10)
        self.assertIn("\033[2J", output.getvalue())
        self.assertIn("\033[1;1Hstable", output.getvalue())

    def test_colored_lines_are_clipped_to_width(self):
        output = io.StringIO()
        screen = TerminalRenderer(output)
        screen.paint(["\033[31mabcdefgh\033[0m"], 4, 5)
        self.assertIn("abcd", output.getvalue())
        self.assertNotIn("efgh", output.getvalue())


if __name__ == "__main__":
    unittest.main()
