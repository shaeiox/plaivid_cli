from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from plaivid_cli.domain.inventory import merge_inventory
from plaivid_cli.domain.models import CollectionStatus
from plaivid_cli.infrastructure.pvm.parsers import (
    parse_metrics,
    parse_object_inventory,
    parse_process_rows,
    parse_sball_status,
    parse_tap_mapping,
    parse_vm_detail,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_object_inventory_parses_defined_facts_only() -> None:
    root = ET.parse(FIXTURES / "objects.xml").getroot()
    result = parse_object_inventory(root)
    assert result.status is CollectionStatus.CURRENT
    assert [item.name for item in result.value] == ["test-vm", "offline-vm"]
    assert result.value[0].vcpu == 4
    assert result.value[0].mem_mb == 8192
    assert result.value[0].state == "started"


def test_duplicate_and_invalid_object_uuids_mark_partial_and_are_excluded() -> None:
    root = ET.fromstring(
        "<description><pvm_vmm_obj><uuid>bad</uuid></pvm_vmm_obj>"
        "<pvm_vmm_obj><uuid>481e458c-c6ba-4fe7-88f6-26a59e416568</uuid></pvm_vmm_obj>"
        "<pvm_vmm_obj><uuid>481e458c-c6ba-4fe7-88f6-26a59e416568</uuid></pvm_vmm_obj>"
        "</description>"
    )
    result = parse_object_inventory(root)
    assert result.status is CollectionStatus.PARTIAL
    assert result.value == ()
    assert len(result.quality_issues) == 2


def test_running_process_rows_are_separate_and_unmatched_rows_are_retained() -> None:
    result = parse_process_rows((FIXTURES / "running-vms.txt").read_text())
    assert result.status is CollectionStatus.CURRENT
    assert len(result.value) == 2
    objects = parse_object_inventory(ET.parse(FIXTURES / "objects.xml").getroot())
    merged = merge_inventory(objects.value, result.value, process_available=True)
    first = next(row for row in merged.records if row.name == "test-vm")
    assert first.object.state == "started"
    assert first.process is not None and first.process.pid == 1234
    assert len(merged.unmatched_process_rows) == 1
    assert all(row.name != "process-only" for row in merged.records)


def test_missing_process_evidence_does_not_overwrite_or_invent_state() -> None:
    objects = parse_object_inventory(ET.parse(FIXTURES / "objects.xml").getroot())
    merged = merge_inventory(objects.value, (), process_available=True)
    started = next(row for row in merged.records if row.name == "test-vm")
    assert started.state == "started"
    assert started.state_disagreed is True

    unavailable = merge_inventory(objects.value, (), process_available=False)
    started_unavailable = next(row for row in unavailable.records if row.name == "test-vm")
    assert started_unavailable.state_disagreed is False


def test_sball_parser_preserves_quorate_without_health_claims() -> None:
    root = ET.fromstring(
        "<description><sball-config><cluster><node><name>node-a</name>"
        "<sball-state>quorate</sball-state><node-state>online</node-state>"
        "<resource-usage><cpus><cpu>20</cpu><cpu>40</cpu></cpus>"
        "<ram><used>1024</used><total>2048</total></ram></resource-usage>"
        "</node></cluster></sball-config></description>"
    )
    result = parse_sball_status(root)
    assert result.value is not None
    assert result.value.sball_state == "quorate"
    assert result.value.cpu_pct == 30
    assert result.value.ram_total_bytes == 2048


def test_metrics_parser_does_not_default_missing_values_to_zero() -> None:
    root = ET.fromstring("<description><metrics><network_info/></metrics></description>")
    result = parse_metrics(root)
    assert result.value is not None
    assert result.value.cpu_pct is None
    assert result.value.memory_total_bytes is None


def test_selected_detail_is_uuid_scoped_and_extracts_supported_fields() -> None:
    root = ET.fromstring(
        "<description><pvm_vmm_obj><uuid>481e458c-c6ba-4fe7-88f6-26a59e416568</uuid>"
        "<name>test-vm</name><virtual_machine><hardware><cpu><vcpu><socket>1</socket>"
        "<core>2</core><thread>2</thread></vcpu></cpu><memory><size>4096</size></memory>"
        "<console><type>spice</type><port>5900</port></console></hardware></virtual_machine>"
        "</pvm_vmm_obj></description>"
    )
    result = parse_vm_detail(root, "481e458c-c6ba-4fe7-88f6-26a59e416568")
    assert result.value is not None
    assert result.value.name == "test-vm"
    assert result.value.vcpu == 4
    assert result.value.memory_mb == 4096
    assert result.value.console is not None and result.value.console.port == 5900


def test_tap_mapping_is_parsed_only_when_requested_separately() -> None:
    root = ET.fromstring(
        "<description><pvm_vmm_obj><name>test-vm</name><virtual_machine><hardware>"
        "<net_adaptor_list><net_adaptor><tap_name>tap-test</tap_name></net_adaptor>"
        "</net_adaptor_list></hardware></virtual_machine></pvm_vmm_obj></description>"
    )
    result = parse_tap_mapping(root)
    assert result.value == {"tap-test": "test-vm"}
