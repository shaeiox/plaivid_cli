import xml.etree.ElementTree as ET
from pathlib import Path

from plaivid_cli.domain.models import CollectionStatus
from plaivid_cli.infrastructure.pvm.parsers import parse_metrics

FIXTURE = Path(__file__).parents[1] / "fixtures" / "monitoring-metrics.xml"


def _metrics():
    root = ET.parse(FIXTURE).getroot()
    result = parse_metrics(root)
    assert result.status is CollectionStatus.CURRENT
    return result.value


def test_system_kernel_and_identity_fields():
    m = _metrics()
    assert m.hostname == "spongebob"
    assert m.host_id == "00000000-0000-5355-4534-303452313457"
    assert m.platform_family == "rhel"
    assert m.kernel_version == "5.14.0-687.58.1.el9_8.x86_64"
    assert m.virtualization == "kvm host"
    assert m.boot_time == "2026-11-04T06:37:16Z"
    assert m.uptime == "0 days, 01:54:34"
    assert m.uptime_seconds == 6874


def test_load_process_and_kernel_counters():
    m = _metrics()
    assert (m.cpu_count, m.run_queue, m.blocked_tasks, m.total_tasks) == (24, 14, 0, 791)
    assert m.blocked_percent == 0.0
    assert (m.num_processes, m.num_threads, m.open_fds) == (529, 791, 2060)
    assert (m.context_switches, m.interrupts, m.forks) == (33282361, 20618322, 47863)
    assert m.process_total == 529


def test_temperatures_keep_negative_capable_values_and_users_are_listed():
    m = _metrics()
    assert [(t.sensor, t.celsius) for t in m.temperatures] == [
        ("acpitz", 8.3), ("coretemp_package_id_0", 43.0), ("tg3", 51.0),
    ]
    assert [(u.user, u.terminal, u.host) for u in m.users] == [
        ("root", "tty1", None), ("shaiya", "pts/0", "172.16.40.243"),
    ]


def test_processes_sorted_by_cpu_and_full_command_is_never_stored():
    m = _metrics()
    assert [p.pid for p in m.processes] == [202, 101]
    assert m.processes[0].command == "plaivid" and m.processes[0].cpu_pct == 5.42
    assert m.processes[1].state == "sleep" and m.processes[1].username == "root"
    assert "FAKE-TOKEN" not in repr(m)


def test_missing_blocks_stay_none():
    result = parse_metrics(ET.fromstring("<description><metrics/></description>"))
    assert result.value.total_tasks is None and result.value.processes == ()
