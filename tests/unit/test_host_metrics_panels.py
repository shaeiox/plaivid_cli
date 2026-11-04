import xml.etree.ElementTree as ET
from pathlib import Path

from plaivid_cli.domain.models import HostMetrics
from plaivid_cli.infrastructure.pvm.parsers import parse_metrics
from plaivid_cli.presentation import host_metrics as hm

FIXTURE = Path(__file__).parents[1] / "fixtures" / "monitoring-metrics.xml"


def _metrics() -> HostMetrics:
    return parse_metrics(ET.parse(FIXTURE).getroot()).value


def test_bodies_render_parsed_values_and_never_the_token():
    m = _metrics()
    bodies = {
        "system": hm.system_body(m),
        "cpu": hm.cpu_body(m),
        "tasks": hm.tasks_body(m),
        "temps": hm.temperature_body(m),
        "sessions": hm.sessions_body(m),
        "procs": hm.processes_body(m),
        "commands": hm.commands_body(m),
    }
    text = "\n".join(line for lines in bodies.values() for line in lines)
    assert any("kvm host" in line for line in bodies["system"])
    assert any("Run queue" in line and "14" in line for line in bodies["cpu"])
    assert any("Processes" in line and "529" in line for line in bodies["tasks"])
    assert any("tg3" in line and "51.0" in line for line in bodies["temps"])
    assert any("172.16.40.243" in line for line in bodies["sessions"])
    assert any("plaivid" in line for line in bodies["procs"])
    assert any("plaivid" in line and "×1" in line for line in bodies["commands"])
    assert "FAKE-TOKEN" not in text and "sbell" not in text


def test_missing_values_render_as_dash_not_zero():
    empty = HostMetrics()
    assert any("Cores" in line and "—" in line for line in hm.cpu_body(empty))
    assert not any(line.split(":")[-1].strip() in ("0", "0%", "0.0%") for line in hm.cpu_body(empty))
    assert hm.network_body(None) == hm.storage_body(None) == hm.processes_body(None) == hm.commands_body(None) == ["No current monitoring values."]


def test_bar_and_size_helpers():
    assert hm.bar(None) == "—"
    assert hm.bar(0, 10) == "░" * 10
    assert hm.bar(100, 10) == "█" * 10
    assert hm.size(None) == "—" and hm.size(1536) == "1.5 KiB"


def test_finish_appends_status_and_redacts():
    text = hm.finish(["Host ID  : x"], "current")
    assert text.splitlines() == ["Host ID  : x", "current"]
