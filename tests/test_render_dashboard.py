"""Regression tests for the responsive dashboard presentation."""

import unittest
from unittest import mock

from plaivid_cli import render
from plaivid_cli.vms import VM
from plaivid_cli.orchestrator import App


class DashboardTests(unittest.TestCase):
    def test_compact_height_mode_preserves_inventory_and_drops_rail(self):
        vm = VM("a" * 36, "test-vm")
        vm.state = "started"
        vm.index = 1
        output = render.dashboard({}, [vm], compact=True)
        self.assertIn("test-vm", output)
        self.assertIn("Commands:", output)
        self.assertNotIn("SELECTED VM", output)
        with mock.patch.object(render, "term_width", return_value=100):
            self.assertLessEqual(max(render._vis(line) for line in
                                     render.dashboard({}, [vm], compact=True).splitlines()), 100)

    def test_page_scroll_moves_by_viewport_and_never_goes_negative(self):
        app = App()
        terminal = type("Terminal", (), {"lines": 20})()
        with mock.patch("plaivid_cli.orchestrator.shutil.get_terminal_size",
                        return_value=terminal):
            app._scroll_page(-1)
            self.assertEqual(app.scroll_offset, 0)
            app._scroll_page(1)
            self.assertEqual(app.scroll_offset, 16)
            app._scroll_page(-1)
            self.assertEqual(app.scroll_offset, 0)

    def test_uptime_format_and_long_box_content(self):
        self.assertEqual(render.format_uptime(0), "0s")
        self.assertEqual(render.format_uptime(604800 + 86400 + 3661),
                         "1w 1d 1h 1m 1s")
        text = "long-value-" * 12 + "tail-marker"
        with mock.patch.object(render, "term_width", return_value=60):
            output = render.frame("Long title " + text, [text])
        self.assertIn("tail-marker", output)
        self.assertNotIn("...", output)

    def test_empty_inventory_and_missing_metrics_render(self):
        output = render.dashboard({}, [])
        self.assertIn("VIRTUAL MACHINES", output)
        self.assertIn("No virtual machines found", output)
        self.assertIn("COMMANDS", output)
        self.assertIn("0 total", output)
        self.assertIn("HOST", output)
        self.assertIn("RESOURCES", output)

    def test_vm_details_and_status_render(self):
        vm = VM("abcd-uuid", "test-vm")
        vm.state = "started"
        vm.vcpu = 2
        vm.mem_mb = 2048
        vm.index = 1
        output = render.dashboard({}, [vm], "uptime ↓", "refresh complete")
        self.assertIn("SELECTED VM", output)
        self.assertIn("test-vm", output)
        self.assertIn("refresh complete", output)
        self.assertIn("Sorted by uptime", output)

    def test_overview_uses_dashboard_panels_responsively(self):
        snap = {"hostname": "pvm-host", "uptime_human": "2 days",
                "cpu_pct": 3, "logical_cores": 8, "physical_cores": 4,
                "host_uptime_seconds": 90061, "sballd_uptime_seconds": 3661,
                "sball_state": "running",
                "mem_pct": 45, "mem_used_gb": 14, "mem_total_gb": 31,
                "swap_total_gb": 0, "load1": 0.1, "load5": 0.2,
                "load15": 0.3, "storage": []}
        agg = {"total": 1, "running": 1, "stopped": 0, "off": 0,
               "vcpu_run": 2, "vcpu_total": 2, "mem_run_mb": 2048,
               "mem_total_mb": 2048}
        for width in (20, 30, 40, 80, 120):
            with mock.patch.object(render, "term_width", return_value=width):
                output = render.overview(snap, None, {}, agg, "*")
            self.assertIn("LIVE OVERVIEW", output)
            self.assertIn("VIRTUAL MACHINES", output)
            self.assertIn("NETWORK", output)
            self.assertIn("STORAGE", output)
            self.assertIn("8 logical cores", output)
            self.assertIn("4 physical cores", output)
            self.assertIn("1m: 0.10", output)
            self.assertIn("0.20", output)
            self.assertIn("15m: 0.30", output)
            self.assertIn("Host 1d 1h 1m 1s", output)
            self.assertIn("sballd 1h 1m 1s", output)
            self.assertLessEqual(max(render._vis(line)
                                     for line in output.splitlines()), width)

    def test_narrow_terminal_stacks_content_without_overflow(self):
        vm = VM("abcd-uuid", "test-vm")
        vm.state = "off"
        vm.index = 1
        for width in (20, 30, 40, 44, 45, 54, 55, 60, 80, 100, 120, 160):
            with mock.patch.object(render, "term_width", return_value=width):
                output = render.dashboard({}, [vm])
            self.assertIn("SELECTED VM", output)
            self.assertIn("VM ACTIONS", output)
            self.assertIn("RESOURCES", output)
            self.assertLessEqual(max(render._vis(line)
                                     for line in output.splitlines()), width)


if __name__ == "__main__":
    unittest.main()
