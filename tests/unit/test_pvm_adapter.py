from __future__ import annotations

from pathlib import Path

from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import Action, ProcessObservation
from plaivid_cli.infrastructure.process import ProcessResult
from plaivid_cli.infrastructure.pvm.adapter import LocalPvmAdapter
from plaivid_cli.infrastructure.pvm.sbell import SbellClient

UUID_A = "481e458c-c6ba-4fe7-88f6-26a59e416568"
FIXTURES = Path(__file__).parents[1] / "fixtures"


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def run(self, argv, *, timeout=None):
        args = tuple(argv)
        self.calls.append(args)
        if "objects" in args:
            output = "<response><status>success</status>" + (FIXTURES / "objects.xml").read_text() + "</response>"
        elif "pvm-running-vms" in args[0]:
            output = (FIXTURES / "running-vms.txt").read_text()
        else:
            output = "<response><status>success</status><action_id>fake-1</action_id><description /></response>"
        return ProcessResult(0, output, "", False, False, 0.001)


def _adapter() -> tuple[LocalPvmAdapter, FakeRunner]:
    runner = FakeRunner()
    sbell = SbellClient(("sudo", "sbell"), runner)  # fake runner, never launched
    return LocalPvmAdapter(sbell, runner, ("pvm-running-vms",), allow_credential_argv=True), runner


def test_adapter_uses_existing_batched_objects_and_separate_process_helper() -> None:
    adapter, runner = _adapter()
    objects = adapter.list_objects("fake-token")
    processes = adapter.list_processes()
    assert len(objects.value) == 2
    assert len(processes.value) == 2
    assert runner.calls[0][:4] == ("sudo", "sbell", "user", "objects")
    assert runner.calls[1] == ("pvm-running-vms",)
    assert runner.calls[0][-1] == "fake-token"


def test_adapter_dispatches_only_existing_action_and_canonical_uuid() -> None:
    adapter, runner = _adapter()
    reply = adapter.dispatch_action("fake-token", Action.START, UUID_A.upper())
    assert reply.status == "success"
    args = runner.calls[-1]
    assert args[2:4] == ("vm", "start")
    assert "<vm_key>" + UUID_A + "</vm_key>" in args[4]
    assert args[-1] == "fake-token"
    assert "session_delete_uuid" not in " ".join(args)


def test_all_six_lifecycle_actions_use_only_repository_evidenced_argv_forms() -> None:
    adapter, runner = _adapter()
    for action in Action:
        adapter.dispatch_action("fake-token", action, UUID_A.upper())
        args = runner.calls[-1]
        assert args[2:4] == ("vm", action.value)
        assert f"<vm_key>{UUID_A}</vm_key>" in args[4]
        if action is Action.START:
            assert "<host>auto</host>" in args[4]
            assert "<version_enable>no</version_enable>" in args[4]
        else:
            assert args[4] == f"<vm_key>{UUID_A}</vm_key>"
        assert args[-1] == "fake-token"


def test_truncated_process_output_is_partial_even_when_prefix_ends_at_valid_rows() -> None:
    class TruncatedRunner(FakeRunner):
        def run(self, argv, *, timeout=None):
            result = super().run(argv, timeout=timeout)
            return ProcessResult(
                result.returncode,
                result.stdout,
                result.stderr,
                True,
                result.stderr_truncated,
                result.elapsed_seconds,
            )

    runner = TruncatedRunner()
    adapter = LocalPvmAdapter(
        SbellClient(("sudo", "sbell"), runner), runner, ("pvm-running-vms",)
    )
    result = adapter.list_processes()
    assert result.status.value == "partial"
    assert "output was truncated" in result.error
    assert "output was truncated" in result.quality_issues[0]


def test_running_process_result_is_typed_and_source_separate() -> None:
    adapter, _ = _adapter()
    result = adapter.list_processes()
    assert isinstance(result.value[0], ProcessObservation)
    assert result.source == "pvm-running-vms"


def test_credential_argv_gate_blocks_before_any_child_process() -> None:
    runner = FakeRunner()
    adapter = LocalPvmAdapter(
        SbellClient(("sudo", "sbell"), runner), runner, ("pvm-running-vms",)
    )
    try:
        adapter.login("user", "password-secret")
    except AppError as error:
        assert error.code == "CREDENTIAL_ARGV_ACK_REQUIRED"
        assert "password-secret" not in str(error)
    else:
        raise AssertionError("login should require explicit argv-risk acknowledgement")
    try:
        adapter.list_objects("token-secret")
    except AppError as error:
        assert error.code == "CREDENTIAL_ARGV_ACK_REQUIRED"
        assert "token-secret" not in str(error)
    else:
        raise AssertionError("token-bearing read should require explicit argv-risk acknowledgement")
    assert runner.calls == []


def test_session_limit_is_reported_without_retry_or_session_eviction() -> None:
    class SessionLimitRunner:
        def __init__(self):
            self.calls = []

        def run(self, argv, *, timeout=None):
            self.calls.append(tuple(argv))
            output = (
                "<response><status>failure</status><description>"
                "<errno>185</errno><what>session limit reached</what>"
                "</description></response>"
            )
            return ProcessResult(0, output, "", False, False, 0.001)

    runner = SessionLimitRunner()
    adapter = LocalPvmAdapter(
        SbellClient(("sudo", "sbell"), runner),
        runner,
        ("pvm-running-vms",),
        allow_credential_argv=True,
    )
    try:
        adapter.login("operator", "synthetic-password")
    except AppError as error:
        assert error.code == "PVM_LOGIN_185"
        assert "synthetic-password" not in str(error)
    else:
        raise AssertionError("session limit response unexpectedly logged in")
    assert len(runner.calls) == 1
    assert "session_delete_uuid" not in " ".join(runner.calls[0])


class FailedRunner(FakeRunner):
    def run(self, argv, *, timeout=None):
        self.calls.append(tuple(argv))
        output = (
            "<response><status>failed</status><action_id>fake-2</action_id>"
            "<description><mid>vm</mid><aid/><errno>146</errno>"
            "<what>VM 'test-vm' is already off</what></description></response>"
        )
        return ProcessResult(0, output, "", False, False, 0.001)


def test_failed_vm_envelope_is_parsed_into_reply_with_errno_and_message() -> None:
    runner = FailedRunner()
    sbell = SbellClient(("sudo", "sbell"), runner)
    adapter = LocalPvmAdapter(sbell, runner, ("pvm-running-vms",), allow_credential_argv=True)
    reply = adapter.dispatch_action("fake-token", Action.STOP, UUID_A)
    assert reply.status == "failed"
    assert reply.errno == "146"
    assert reply.message == "VM 'test-vm' is already off"
    assert runner.calls[-1] == ("sudo", "sbell", "vm", "stop", f"<vm_key>{UUID_A}</vm_key>", "fake-token")


def test_dashboard_uses_existing_token_gate_and_preserves_requested_xml() -> None:
    class DashboardRunner(FakeRunner):
        def run(self, argv, *, timeout=None):
            self.calls.append(tuple(argv))
            return ProcessResult(
                0,
                "<response><status>success</status><description><host_list><host_dashboard>"
                "<name>node-a</name><id>3</id><cpus><cpu>Xeon</cpu></cpus>"
                "<ram><free>8</free><used>2</used><total>10</total></ram>"
                "</host_dashboard></host_list></description></response>",
                "", False, False, 0.001,
            )

    runner = DashboardRunner()
    adapter = LocalPvmAdapter(SbellClient(("sudo", "sbell"), runner), runner, ("pvm-running-vms",), allow_credential_argv=True)
    sample = adapter.dashboard("fake-token").value
    assert sample.host_name == "node-a" and sample.cpu_info == ("Xeon",)
    assert sample.ram_total_raw == "10" and sample.vdis == ()
    args = runner.calls[0]
    assert args[:4] == ("sudo", "sbell", "user", "objects")
    assert "<query_path>/plaivid/overview/pvm_overview_dashboard</query_path>" in args[4]
    assert args[-1] == "fake-token"
    gated = LocalPvmAdapter(SbellClient(("sudo", "sbell"), runner), runner, ("pvm-running-vms",))
    try:
        gated.dashboard("secret")
    except AppError as error:
        assert error.code == "CREDENTIAL_ARGV_ACK_REQUIRED"
    else:
        raise AssertionError("dashboard must retain the existing token gate")
    assert len(runner.calls) == 1
