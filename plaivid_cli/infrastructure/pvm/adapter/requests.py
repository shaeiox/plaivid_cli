"""Repository-evidenced PVM command shapes and XML request construction."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from plaivid_cli.domain.models import Action, canonical_uuid

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


def _xml_text(tag: str, value: str) -> str:
    element = ET.Element(tag)
    element.text = value
    return ET.tostring(element, encoding="unicode", short_empty_elements=False)


def _login_params(username: str, password: str) -> str:
    root = ET.Element("params")
    ET.SubElement(root, "username").text = username
    ET.SubElement(root, "password").text = password
    return ET.tostring(root, encoding="unicode", short_empty_elements=False)


def _action_params(action: Action, uuid: str) -> str:
    key = canonical_uuid(uuid)
    if action is Action.START:
        # This parameter structure is copied from the existing source action.
        return (
            f"<vm_start><vm_key>{key}</vm_key><host>auto</host>"
            "<version_start><version_enable>no</version_enable>"
            "<version_vkey></version_vkey></version_start>"
            "<exit_from_replicate>yes</exit_from_replicate></vm_start>"
        )
    return _xml_text("vm_key", key)
