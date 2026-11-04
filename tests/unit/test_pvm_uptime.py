import time
from datetime import UTC, datetime
from types import SimpleNamespace

from plaivid_cli.application.overview import OverviewHistory
from plaivid_cli.domain.models import ApplicationSnapshot, CollectionStatus, SectionSnapshot
from plaivid_cli.domain.overview import DashboardSample, LocalHostSample
from plaivid_cli.infrastructure.process import ProcessError
from plaivid_cli.infrastructure.pvm.adapter import SBALLD_STATUS_ARGV, LocalPvmAdapter
from plaivid_cli.infrastructure.pvm.uptime import sball_uptime_seconds
from plaivid_cli.presentation.overview import _uptime, cards

STATUS = """\
● sballd.service - PVM Cluster Engine (aka. Sball)

     Loaded: loaded (/usr/lib/systemd/system/sballd.service; enabled; preset: disabled)

     Active: active (running) since Wed 2026-11-04 10:27:39 +0330; 58min ago

   Main PID: 21487 (sballd)
"""


def test_uptime_is_elapsed_time_since_start_with_timezone_offset():
    # 10:27:39 +03:30 is 06:57:39 UTC.
    now = datetime(2026, 11, 4, 7, 55, 39, tzinfo=UTC)
    assert sball_uptime_seconds(STATUS, now) == 58 * 60


def test_uptime_is_none_unless_service_is_running_and_parsable():
    now = datetime(2026, 11, 4, 8, 0, 0, tzinfo=UTC)
    assert sball_uptime_seconds(STATUS.replace("active (running)", "inactive (dead)"), now) is None
    assert sball_uptime_seconds("Unit sballd.service could not be found.", now) is None
    assert sball_uptime_seconds(STATUS, datetime(2026, 11, 4, 1, 0, 0)) is None  # naive clock
    assert sball_uptime_seconds(STATUS, datetime(2026, 11, 4, 0, 0, 0, tzinfo=UTC)) is None  # future start


def test_format_is_weeks_days_hours_minutes_seconds():
    assert _uptime(None) == "N/A"
    assert _uptime(0) == "0w 0d 0h 0m 0s"
    assert _uptime(3600 + 60 + 1) == "0w 0d 1h 1m 1s"
    assert _uptime(2 * 604800 + 3 * 86400 + 4 * 3600 + 5 * 60 + 6) == "2w 3d 4h 5m 6s"


class Runner:
    def __init__(self, stdout=STATUS, error=None):
        self.stdout, self.error, self.calls = stdout, error, []

    def run(self, argv, *, timeout=None):
        self.calls.append((tuple(argv), timeout))
        if self.error:
            raise self.error
        return SimpleNamespace(stdout=self.stdout)


class Monitor:
    def host(self):
        return LocalHostSample(hostname="spongebob", memory_total=1, load1=0.1)


def _adapter(runner):
    adapter = LocalPvmAdapter(None, runner, ("pvm-running-vms",))
    adapter._local_monitor = Monitor()
    return adapter


def test_adapter_reads_sballd_status_without_shell_and_fills_uptime():
    runner = Runner()
    result = _adapter(runner).local_host()
    assert runner.calls[0][0] == SBALLD_STATUS_ARGV == ("systemctl", "status", "sballd", "--no-pager")
    assert result.value.pvm_uptime_seconds is not None and result.value.pvm_uptime_seconds > 0
    assert result.status is CollectionStatus.CURRENT


def test_adapter_leaves_uptime_unknown_when_systemctl_fails():
    result = _adapter(Runner(error=ProcessError("missing"))).local_host()
    assert result.value.pvm_uptime_seconds is None
    assert result.value.hostname == "spongebob"


def test_host_card_shows_pvm_uptime_and_drops_api_warning_and_proc_disclaimer():
    now = time.monotonic()
    local = SectionSnapshot(
        "local_host", LocalHostSample(hostname="spongebob", pvm_uptime_seconds=3725), None,
        CollectionStatus.CURRENT, datetime.now(UTC), datetime.now(UTC), 1,
        latency_seconds=0.01, succeeded_monotonic=now, attempted_monotonic=now,
    )
    dashboard = SectionSnapshot(
        "dashboard", DashboardSample(host_name="spongebob", host_id="ID-1"), None,
        CollectionStatus.UNAVAILABLE, None, None, 0,
    )
    snapshot = ApplicationSnapshot(generation=1, created_at=datetime.now(UTC), sections=(local, dashboard))
    lines = cards(snapshot, OverviewHistory(), 3).get("host-identity", "").splitlines()
    assert lines[0].startswith("LOCAL  spongebob")
    assert lines[1] == "PVM Uptime  0w 0d 1h 2m 5s"
    assert len(lines) == 2
