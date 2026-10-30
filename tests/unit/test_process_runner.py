from __future__ import annotations

import os
import sys
import time

import pytest

from plaivid_cli.infrastructure.process import ProcessRunner, ProcessStartError, ProcessTimeout


def test_process_runner_preserves_argument_boundaries() -> None:
    runner = ProcessRunner(timeout=2)
    result = runner.run(
        [sys.executable, "-c", "import sys; print(repr(sys.argv[1:]))", "a b; $(false)"]
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "['a b; $(false)']"


def test_process_runner_bounds_retained_output() -> None:
    runner = ProcessRunner(timeout=2, max_output_bytes=64)
    result = runner.run([sys.executable, "-c", "print('x' * 10000)"])
    assert result.returncode == 0
    assert len(result.stdout.encode()) <= 64
    assert result.stdout_truncated is True


def test_process_runner_times_out_and_reaps_direct_child() -> None:
    runner = ProcessRunner(timeout=0.05, terminate_grace=0.2)
    started = time.monotonic()
    with pytest.raises(ProcessTimeout):
        runner.run([sys.executable, "-c", "import time; time.sleep(10)"])
    assert time.monotonic() - started < 2


def test_process_runner_timeout_kills_descendant_process_group(tmp_path) -> None:
    if os.name != "posix":
        pytest.skip("process-group cleanup is POSIX-specific")
    marker = tmp_path / "grandchild-survived"
    grandchild = (
        "import time; time.sleep(0.6); "
        f"open({str(marker)!r}, 'w', encoding='utf-8').write('alive')"
    )
    parent = (
        "import subprocess,sys,time; "
        f"subprocess.Popen([sys.executable, '-c', {grandchild!r}]); "
        "time.sleep(10)"
    )
    with pytest.raises(ProcessTimeout):
        ProcessRunner(timeout=0.1, terminate_grace=0.5).run([sys.executable, "-c", parent])
    time.sleep(0.7)
    assert not marker.exists()


def test_process_runner_does_not_inherit_ambient_secret_environment(monkeypatch) -> None:
    monkeypatch.setenv("PLAIVID_TEST_SECRET", "do-not-inherit")
    result = ProcessRunner(timeout=2).run(
        [sys.executable, "-c", "import os; print(os.getenv('PLAIVID_TEST_SECRET', 'missing'))"]
    )
    assert result.stdout.strip() == "missing"


def test_process_runner_preserves_nonzero_exit_status() -> None:
    result = ProcessRunner(timeout=2).run([sys.executable, "-c", "raise SystemExit(7)"])
    assert result.returncode == 7


def test_process_runner_reports_missing_executable_without_argv() -> None:
    with pytest.raises(ProcessStartError, match="configured local command"):
        ProcessRunner(timeout=1).run(["/definitely/not/a/plaivid-command"])


@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), float("-inf")])
def test_process_runner_rejects_non_finite_timeouts_before_spawn(timeout: float) -> None:
    with pytest.raises(ValueError, match="finite and positive"):
        ProcessRunner(timeout=timeout)
    runner = ProcessRunner(timeout=1)
    with pytest.raises(ValueError, match="finite and positive"):
        runner.run([sys.executable, "-c", "raise SystemExit(0)"], timeout=timeout)


def test_process_runner_rejects_empty_argv() -> None:
    runner = ProcessRunner(timeout=1)
    with pytest.raises(ValueError, match="argv"):
        runner.run([])
