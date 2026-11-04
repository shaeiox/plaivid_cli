import xml.etree.ElementTree as ET
from pathlib import Path

from plaivid_cli.domain.models import HostMetrics
from plaivid_cli.infrastructure.pvm.parsers import parse_metrics
from plaivid_cli.presentation import host_metrics as hm

FIXTURE = Path(__file__).parents[1] / "fixtures" / "monitoring-metrics.xml"


def _metrics() -> HostMetrics:
    return parse_metrics(ET.parse(FIXTURE).getroot()).value


def test_every_panel_renders_parsed_values_and_never_the_token():
    m = _metrics()
    panels = {
        "system": hm.system_panel(m, "current"),
        "cpu": hm.cpu_panel(m),
        "tasks": hm.tasks_panel(m),
        "temps": hm.temperature_panel(m),
        "sessions": hm.sessions_panel(m),
        "procs": hm.processes_panel(m),
    }
    text = "\n".join(panels.values())
    assert "SYSTEM  ·  current" in panels["system"]
    assert "spongebob" in panels["system"] and "kvm host" in panels["system"]
    assert "0 days, 01:54:34 (6,874 s)" in panels["system"]
    assert "Run queue   14" in panels["cpu"] and "24" in panels["cpu"]
    assert "Processes   529" in panels["tasks"] and "Open fds    2,060" in panels["tasks"]
    assert "Hottest     tg3  51.0 °C" in panels["temps"]
    assert "172.16.40.243" in panels["sessions"]
    assert "plaivid" in panels["procs"] and "529 total" in panels["procs"]
    assert "FAKE-TOKEN" not in text and "sbell" not in text


def test_missing_values_render_as_dash_not_zero():
    empty = HostMetrics()
    cpu = hm.cpu_panel(empty)
    assert "Usage       —" in cpu
    assert "0.0%" not in cpu and "0%" not in cpu
    assert "No current monitoring values." in hm.memory_panel(None)


def test_bar_and_size_helpers():
    assert hm.bar(None) == "—"
    assert hm.bar(0, 10) == "╺" * 10
    assert hm.bar(100, 10) == "━" * 10
    assert hm.size(None) == "—" and hm.size(1536) == "1.5 KiB"
