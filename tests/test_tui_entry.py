"""Full-screen terminal lifecycle and default-entry tests."""

import io
import unittest
from unittest import mock

from plaivid_cli import orchestrator


class TuiEntryTests(unittest.TestCase):
    def test_tui_and_no_args_enter_interactive_mode(self):
        with mock.patch.object(orchestrator.App, "run_interactive", return_value=7) as run:
            self.assertEqual(orchestrator.main([]), 7)
            self.assertEqual(orchestrator.main(["tui"]), 7)
            self.assertEqual(orchestrator.main(["--tui"]), 7)
        self.assertEqual(run.call_count, 3)

    def test_escape_sequences_are_consumed_without_leaking_input_bytes(self):
        app = orchestrator.App()
        fd = 41

        for sequence, expected in ((b"[6~tail", "[6~"),
                                   (b"OAcommand", "OA"),
                                   (b"[5;2~text", "[5;2~")):
            remaining = bytearray(sequence)

            def available(readers, _write, _errors, _timeout):
                return (readers if remaining else [], [], [])

            def read_byte(_fd, _size):
                return bytes([remaining.pop(0)]) if remaining else b""

            with mock.patch.object(orchestrator.os, "read", side_effect=read_byte):
                self.assertEqual(app._read_escape_sequence(available, fd), expected)
            self.assertEqual(bytes(remaining), sequence[len(expected):])

    def test_mouse_wheel_codes_are_intercepted(self):
        app = orchestrator.App()
        self.assertEqual(app._read_mouse_scroll("[<64;10;4M", None, 41), -1)
        self.assertEqual(app._read_mouse_scroll("[<65;10;4M", None, 41), 1)
        self.assertEqual(app._read_mouse_scroll("[<0;10;4m", None, 41), 0)

    def test_fullscreen_buffer_and_cursor_are_restored(self):
        output = io.StringIO()
        output.isatty = lambda: True
        input_stream = io.StringIO()
        input_stream.isatty = lambda: True
        app = orchestrator.App()
        with mock.patch.object(orchestrator.sys, "stdout", output), \
                mock.patch.object(orchestrator.sys, "stdin", input_stream):
            app._enter_fullscreen()
            self.assertTrue(app._fullscreen)
            app._leave_fullscreen()
            self.assertFalse(app._fullscreen)
        self.assertIn("\033[?1049h", output.getvalue())
        self.assertIn("\033[?1000h\033[?1006h", output.getvalue())
        self.assertIn("\033[?25l", output.getvalue())
        self.assertIn("\033[?1006l\033[?1000l", output.getvalue())
        self.assertIn("\033[?25h\033[?1049l", output.getvalue())


if __name__ == "__main__":
    unittest.main()
