"""Regression tests for the responsive dashboard presentation."""

import unittest
from unittest import mock

from plaivid_cli import render
from plaivid_cli.vms import VM


class DashboardTests(unittest.TestCase):
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

    def test_narrow_terminal_stacks_content_without_overflow(self):
        vm = VM("abcd-uuid", "test-vm")
        vm.state = "off"
        vm.index = 1
        for width in (60, 80, 100, 120, 160):
            with mock.patch.object(render, "term_width", return_value=width):
                output = render.dashboard({}, [vm])
            self.assertIn("SELECTED VM", output)
            self.assertIn("VM ACTIONS", output)
            self.assertIn("RESOURCES", output)
            self.assertLessEqual(max(render._vis(line)
                                     for line in output.splitlines()), width)


if __name__ == "__main__":
    unittest.main()
