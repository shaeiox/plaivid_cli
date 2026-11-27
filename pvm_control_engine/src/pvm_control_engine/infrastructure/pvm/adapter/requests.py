"""Repository-evidenced PVM command shapes and XML request construction."""

from __future__ import annotations

DASHBOARD_QUERY = (
    "<params><query_path>/plaivid/overview/pvm_overview_dashboard</query_path>"
    "<page_size>0</page_size><requested_page>1</requested_page>"
    "<variable_list/><order_by_list/><order_by/><filter_by_list/><filter_by/>"
    "</params>"
)


DESKTOP_QUERY = (
    '<params><query>/objects/object/*[type[text()="pvm_desktop_lite_virtual_desktop"]]'
    "</query></params>"
)


VM_QUERY = (
    "<params><query>/objects/object/pvm_vmm_obj"
    "[type[text()='pvm_vmm_virtual_machine']]</query></params>"
)


ERRNO_HINT = {
    "39": "session missing or expired",
    "40": "permission denied or malformed request",
    "108": "local sbell permission denied",
    "137": "authentication rejected",
    "146": "VM state rejected by PVM",
    "185": "PVM session limit reached; no sessions were removed",
}


SBALLD_STATUS_ARGV = ("systemctl", "status", "sballd", "--no-pager")
