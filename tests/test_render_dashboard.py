"""Regression tests for the data-only dashboard presentation."""

import unittest

from plaivid_cli import render
from plaivid_cli.vms import VM


class DashboardTests(unittest.TestCase):
    def test_empty_inventory_and_missing_metrics_render(self):
        output = render.dashboard({}, [])
        self.assertIn("Virtual machines", output)
        self.assertIn("no VMs found", output)
        self.assertIn("Commands & status", output)
        self.assertIn("0 total", output)

    def test_selected_vm_and_sort_status_render(self):
        vm = VM("abcd-uuid", "test-vm")
        vm.state = "started"
        vm.vcpu = 2
        vm.mem_mb = 2048
        vm.index = 1
        output = render.dashboard({}, [vm], "uptime ↓", "refresh complete")
        self.assertIn("Selected VM", output)
        self.assertIn("test-vm", output)
        self.assertIn("refresh complete", output)
        self.assertIn("sorted by uptime ↓", output)


if __name__ == "__main__":
    unittest.main()
