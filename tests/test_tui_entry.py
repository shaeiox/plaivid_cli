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

        def available(streams, _write, _errors, _timeout):
            stream = streams[0]
            return ([stream] if stream.tell() < len(stream.getvalue()) else [], [], [])

        for sequence, expected in (("[6~tail", "[6~"),
                                   ("OAcommand", "OA"),
                                   ("[5;2~text", "[5;2~")):
            stream = io.StringIO(sequence)
            self.assertEqual(app._read_escape_sequence(available, stream), expected)
            self.assertEqual(stream.read(), sequence[len(expected):])

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
        self.assertIn("\033[?25l", output.getvalue())
        self.assertIn("\033[?25h\033[?1049l", output.getvalue())


if __name__ == "__main__":
    unittest.main()
