from datetime import UTC, datetime
from types import SimpleNamespace

from pvm_control_engine.domain.models import CollectionStatus
from pvm_control_engine.infrastructure.process import ProcessError
from pvm_control_engine.infrastructure.pvm.adapter import SBALLD_STATUS_ARGV, LocalPvmAdapter
from pvm_control_engine.infrastructure.pvm.uptime import sball_uptime_seconds

STATUS = """\
● sballd.service - PVM Cluster Engine (aka. Sball)

     Loaded: loaded (/usr/lib/systemd/system/sballd.service; enabled; preset: disabled)

     Active: active (running) since Wed 2026-11-04 10:27:39 +0330; 58min ago

   Main PID: 21487 (sballd)
"""


def test_uptime_is_elapsed_time_since_start_with_timezone_offset():
    now = datetime(2026, 11, 4, 7, 55, 39, tzinfo=UTC)
    assert sball_uptime_seconds(STATUS, now) == 58 * 60


def test_uptime_is_none_unless_service_is_running_and_parsable():
    now = datetime(2026, 11, 4, 8, 0, 0, tzinfo=UTC)
    assert sball_uptime_seconds(STATUS.replace("active (running)", "inactive (dead)"), now) is None
    assert sball_uptime_seconds("Unit sballd.service could not be found.", now) is None
    assert sball_uptime_seconds(STATUS, datetime(2026, 11, 4, 1, 0, 0)) is None
    assert sball_uptime_seconds(STATUS, datetime(2026, 11, 4, 0, 0, 0, tzinfo=UTC)) is None


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
        from pvm_control_engine.domain.overview import LocalHostSample
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
