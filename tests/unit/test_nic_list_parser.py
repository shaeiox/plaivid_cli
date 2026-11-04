import xml.etree.ElementTree as ET
from pathlib import Path

from plaivid_cli.domain.models import CollectionStatus
from plaivid_cli.infrastructure.pvm.overview import parse_nic_list

FIXTURE = Path(__file__).parents[1] / "fixtures" / "nic-list.xml"


def test_nic_list_maps_linux_device_name_and_pvm_identifier():
    result = parse_nic_list(ET.parse(FIXTURE).getroot())
    assert result.status is CollectionStatus.CURRENT
    assert [nic.name for nic in result.value] == ["eno2", "eno3", "eno4"]
    eno4 = result.value[2]
    assert eno4.identifier == "NIC4"
    assert eno4.mac == "00:00:5e:00:00:04"
    assert eno4.ip is None and eno4.gateway is None
    assert eno4.management == "sball"
    assert eno4.redundancy == "enable=no vlan=0"


def test_record_without_device_or_name_fails_closed():
    xml = "<description><nic_list><nic><name>NIC9</name></nic></nic_list></description>"
    result = parse_nic_list(ET.fromstring(xml))
    assert result.value is None and result.status is CollectionStatus.UNAVAILABLE


def test_empty_nic_list_is_current_with_no_devices():
    result = parse_nic_list(ET.fromstring("<description><nic_list/></description>"))
    assert result.value == () and result.status is CollectionStatus.CURRENT
