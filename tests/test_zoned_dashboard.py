"""Integration checks for list-only scrolling and static screen zones."""

import io
import re
import unittest
from unittest import mock

from plaivid_cli import orchestrator, render
from plaivid_cli.terminal import TerminalRenderer
from plaivid_cli.vms import VM


class TtyBuffer(io.StringIO):
    def isatty(self):
        return True


class ZonedDashboardTests(unittest.TestCase):
    def test_resize_while_list_scrolled_recomputes_frame_once(self):
        app = orchestrator.App()
        app.vms = [VM("uuid-%02d" % n, "vm-%02d" % n) for n in range(20)]
        for index, vm in enumerate(app.vms, 1):
            vm.index = index
            vm.state = "started"
        output = TtyBuffer()
        app._screen = TerminalRenderer(output)
        sizes = [type("Terminal", (), {"columns": 100, "lines": 24})(),
                 type("Terminal", (), {"columns": 100, "lines": 24})(),
                 type("Terminal", (), {"columns": 100, "lines": 30})()]
        with mock.patch.object(orchestrator.sys, "stdin", TtyBuffer()), \
                mock.patch.object(orchestrator.sys, "stdout", output), \
                mock.patch.object(orchestrator.shutil, "get_terminal_size",
                                  side_effect=sizes), \
                mock.patch.object(render, "term_width", return_value=100):
            app.draw()
            app._scroll_page(1)
            app.draw()
            self.assertGreater(app.scroll_offset, 0)
            output.seek(0)
            output.truncate(0)
            app.draw()
        self.assertIn("\033[2J", output.getvalue())

    def test_scroll_paints_list_rows_without_clearing_static_zones(self):
        app = orchestrator.App()
        app.host = {"name": "host", "ip": "10.0.0.1", "cpu_pct": 3,
                    "cpu_count": 8, "load1": 0.1, "load5": 0.2,
                    "load15": 0.3}
        app.vms = []
        for index in range(20):
            vm = VM("uuid-%02d" % index, "vm-%02d" % index)
            vm.index = index + 1
            vm.state = "started"
            app.vms.append(vm)
        output = TtyBuffer()
        app._screen = TerminalRenderer(output)
        terminal = type("Terminal", (), {"columns": 100, "lines": 24})()
        with mock.patch.object(orchestrator.sys, "stdin", TtyBuffer()), \
                mock.patch.object(orchestrator.sys, "stdout", output), \
                mock.patch.object(orchestrator.shutil, "get_terminal_size",
                                  return_value=terminal), \
                mock.patch.object(render, "term_width", return_value=100):
            app.draw()
            self.assertGreater(app.vm_limit, 0)
            static_frame = render.dashboard(
                app.host, app.vms, compact=True, vm_offset=0,
                vm_limit=app.vm_limit).splitlines()
            table_row = next(i + 1 for i, line in enumerate(static_frame)
                             if "VIRTUAL MACHINES" in line)
            output.seek(0)
            output.truncate(0)
            app._scroll_page(1)
            app.draw()

        diff = output.getvalue()
        self.assertNotIn("\033[2J", diff)  # no whole-screen clear on scroll
        self.assertNotIn("\033[1;1H", diff)  # header row is not repainted
        changed_rows = [int(row) for row in re.findall(r"\033\[(\d+);1H", diff)]
        self.assertTrue(changed_rows)
        self.assertTrue(all(row > 1 for row in changed_rows))
        list_rows = set(range(table_row, table_row + app.vm_limit + 3))
        # Row 2 holds a live clock and the final row is the command-input clear.
        self.assertTrue(all(row in list_rows or row in (2, 24)
                            for row in changed_rows), changed_rows)
        self.assertGreater(app.scroll_offset, 0)


if __name__ == "__main__":
    unittest.main()
