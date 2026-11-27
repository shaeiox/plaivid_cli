from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from pvm_control_engine.application.service import EngineService, _safe_value
from pvm_control_engine.bootstrap import _parse_socket_mode, _socket_path, main
from pvm_control_engine.composition import EngineRuntime, build_runtime
from pvm_control_engine.config import ConfigurationError, load_settings
from pvm_control_engine.domain.errors import AppError
from pvm_control_engine.domain.models import Action, PvmSession
from pvm_control_engine.infrastructure.process import ProcessResult
from pvm_control_engine.infrastructure.pvm.adapter.local import LocalPvmAdapter
from pvm_control_engine.infrastructure.pvm.adapter.requests import (
    DASHBOARD_QUERY,
    DESKTOP_QUERY,
    VM_QUERY,
)
from pvm_control_engine.infrastructure.pvm.sbell import SbellClient
from pvm_control_engine.infrastructure.sbell.commands.user.objects import UserObjects
from pvm_control_engine.infrastructure.sbell.commands.vm.kill import KillVM
from pvm_control_engine.ipc.dispatcher import RpcDispatcher
from pvm_control_engine.ipc.server import UnixRpcServer

ROOT = Path(__file__).parents[2]
UUID = "abcdefab-cdef-4abc-8def-abcdefabcdef"


class FakeService:
    def __init__(self):
        self.calls = []

    def list_vms(self):
        self.calls.append(("vm.list",))
        return {"value": []}

    def vm_detail(self, uuid):
        self.calls.append(("vm.get", uuid))
        return {"uuid": uuid}

    def host_status(self):
        return {"status": "current"}

    def host_metrics(self):
        return {"status": "current"}

    def local_host(self):
        return {"status": "current"}

    def nic_samples(self):
        return {"physical_nics": {"status": "current"}, "nic_samples": {"status": "current"}}

    def recent_audit(self, limit):
        return {"entries": [], "limit": limit}

    def desktop_list(self):
        return {"status": "current", "value": []}

    def operate_desktop(self, action, uuids):
        return {"action": action, "uuids": uuids}

    def dashboard(self):
        return {"status": "current"}

    def tap_mapping(self):
        return {"status": "current", "value": {}}

    def nic_list(self):
        return {"status": "current", "value": []}

    def login(self, username, password):
        self.calls.append(("login", username, password))
        return {"username": username}

    def logout(self):
        return {"authenticated": False}

    def operate(self, action, uuid=None, uuids=None):
        self.calls.append((action, uuid if uuid is not None else uuids))
        return {"state": "OUTCOME_UNKNOWN"}


def rpc(path: Path, payload: dict) -> dict:
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(3)
    client.connect(str(path))
    client.sendall(json.dumps(payload, separators=(",", ":")).encode() + b"\n")
    data = bytearray()
    while b"\n" not in data:
        part = client.recv(4096)
        if not part:
            break
        data.extend(part)
    client.close()
    return json.loads(data.split(b"\n", 1)[0])


def start_server(
    tmp_path, service, *, allowed_uids=None, max_workers=2, max_message_bytes=1_048_576
):
    path = tmp_path / "rpc.sock"
    server = UnixRpcServer(
        path,
        RpcDispatcher(service),
        allowed_uids=allowed_uids,
        max_workers=max_workers,
        max_message_bytes=max_message_bytes,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    deadline = time.monotonic() + 3
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert path.exists()
    deadline = time.monotonic() + 3
    while True:
        try:
            rpc(path, {"jsonrpc": "2.0", "id": "ready", "method": "engine.health"})
            break
        except ConnectionRefusedError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.01)
    time.sleep(0.01)
    return path, server, thread


def test_engine_imports_without_ui_project_installed():
    code = """
import importlib.abc, sys
class BlockUI(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".", 1)[0] in {"plaivid_ui", "plaivid_cli"}:
            raise AssertionError("forbidden UI import: " + fullname)
sys.meta_path.insert(0, BlockUI())
import pvm_control_engine.bootstrap
assert "pvm_control_engine.bootstrap" in sys.modules
assert not any(name == "plaivid_ui" or name.startswith("plaivid_ui.") for name in sys.modules)
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, check=True)


def test_safe_dto_serialization_redacts_secrets_but_keeps_audit_command():
    from pvm_control_engine.domain.models import AuditEntry

    entry = AuditEntry("now", "operator", "127.0.0.1", "PVM", "VM stopped", "success", True)
    assert _safe_value(entry)["command"] == "VM stopped"
    assert (
        _safe_value({"password": "secret", "token": "secret", "argv": ["x"], "command": "raw"})
        == {}
    )


def test_socket_mode_configuration_is_octal_and_restrictive():
    assert _parse_socket_mode("0600") == 0o600
    assert _parse_socket_mode("0660") == 0o660
    with pytest.raises(argparse.ArgumentTypeError, match="0600 or 0660"):
        _parse_socket_mode("0666")


def test_socket_path_precedence_preserves_cli_environment_and_state_defaults(monkeypatch):
    from argparse import Namespace

    settings = load_settings({"PLAIVID_STATE_DIR": "/engine-state"})
    args = Namespace(socket=None)
    monkeypatch.setenv("PLAIVID_CONTROL_SOCKET", "/env/engine.sock")
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/runtime")
    assert _socket_path(args, settings) == "/env/engine.sock"
    args.socket = "/cli/engine.sock"
    assert _socket_path(args, settings) == "/cli/engine.sock"
    args.socket = None
    monkeypatch.delenv("PLAIVID_CONTROL_SOCKET")
    assert _socket_path(args, settings) == "/runtime/pvm-control-engine.sock"
    monkeypatch.delenv("XDG_RUNTIME_DIR")
    assert _socket_path(args, settings) == "/engine-state/pvm-control-engine.sock"


def test_main_passes_socket_and_authorization_options_to_composition(monkeypatch, capsys):
    import pvm_control_engine.bootstrap as bootstrap

    settings = load_settings({"PLAIVID_STATE_DIR": "/engine-state"})
    seen = {}
    monkeypatch.setattr(bootstrap, "load_settings", lambda: settings)

    def fail_after_capture(received_settings, socket_path, **kwargs):
        seen.update(settings=received_settings, socket_path=socket_path, **kwargs)
        raise RuntimeError("captured startup settings")

    monkeypatch.setattr(bootstrap, "build_runtime", fail_after_capture)
    assert main(
        ["serve", "--socket", "/cli/engine.sock", "--allow-uid", "19", "--allow-uid", "23", "--socket-mode", "0660", "--max-workers", "3"]
    ) == 2
    assert seen == {
        "settings": settings,
        "socket_path": "/cli/engine.sock",
        "allowed_uids": {os.getuid(), 19, 23},
        "max_workers": 3,
        "socket_mode": 0o660,
    }
    assert "captured startup settings" in capsys.readouterr().err


def test_runtime_owns_serve_and_closes_each_resource_once():
    calls = []

    class Resource:
        def __init__(self, name):
            self.name = name

        def close(self):
            calls.append(f"close:{self.name}")

    class Server(Resource):
        def serve_forever(self):
            calls.append("serve")

    runtime = EngineRuntime(object(), Server("server"), Resource("operations"), Resource("collection"))
    runtime.serve()
    runtime.close()
    runtime.close()
    assert calls == ["serve", "close:server", "close:operations", "close:collection"]


def test_runtime_closes_remaining_resources_if_server_close_fails():
    calls = []

    class FailingServer:
        def close(self):
            calls.append("server")
            raise OSError("close failed")

    class Resource:
        def close(self):
            calls.append("resource")

    runtime = EngineRuntime(object(), FailingServer(), Resource(), Resource())
    with pytest.raises(OSError, match="close failed"):
        runtime.close()
    assert calls == ["server", "resource", "resource"]


def test_engine_composition_registers_each_permitted_vm_action_without_starting_pvm(tmp_path):
    settings = load_settings({"PLAIVID_STATE_DIR": str(tmp_path / "state")})
    runtime = build_runtime(settings, tmp_path / "engine.sock")
    try:
        assert isinstance(runtime.service.registry.vm_action("kill"), KillVM)
        assert all(runtime.service.registry.vm_action(action.value) for action in Action)
        assert set(runtime.service.registry.commands) == {
            "user.login",
            "user.whoami",
            "user.logout",
            "user.objects",
            "sball.show",
            "monitoring.metrics",
            "network.nic_list",
            "local.host_metrics",
            "local.nic_samples",
            "local.audit",
            "desktop.operate",
        }
        assert not any(key.startswith("vm.") for key in runtime.service.registry.commands)
    finally:
        runtime.close()
    assert not (tmp_path / "engine.sock").exists()


def test_composition_failure_closes_coordinators(monkeypatch, tmp_path):
    import pvm_control_engine.composition as composition

    settings = load_settings({"PLAIVID_STATE_DIR": str(tmp_path / "state")})
    created = {}
    real_collection = composition.CollectionCoordinator
    real_operations = composition.VMOperationCoordinator

    class TrackingCollection(real_collection):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            created["collection"] = self
            self.closed = False

        def close(self):
            self.closed = True
            super().close()

    class TrackingOperations(real_operations):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            created["operations"] = self
            self.closed = False

        def close(self):
            self.closed = True
            super().close()

    monkeypatch.setattr(composition, "CollectionCoordinator", TrackingCollection)
    monkeypatch.setattr(composition, "VMOperationCoordinator", TrackingOperations)
    monkeypatch.setattr(
        composition,
        "build_command_registry",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("registry failed")),
    )
    with pytest.raises(RuntimeError, match="registry failed"):
        build_runtime(settings, tmp_path / "engine.sock")
    assert created["operations"].closed
    assert created["collection"].closed


def test_main_configuration_and_composition_errors_keep_exit_code_two(monkeypatch, capsys):
    import pvm_control_engine.bootstrap as bootstrap

    monkeypatch.setattr(bootstrap, "load_settings", lambda: (_ for _ in ()).throw(ConfigurationError("bad config")))
    assert main(["serve"]) == 2
    assert "pvm-control-engine: bad config" in capsys.readouterr().err

    monkeypatch.setattr(bootstrap, "load_settings", lambda: load_settings({}))
    monkeypatch.setattr(bootstrap, "build_runtime", lambda *_a, **_k: (_ for _ in ()).throw(OSError("socket failed")))
    assert main(["serve", "--socket", "/tmp/test-engine.sock"]) == 2
    assert "pvm-control-engine: socket failed" in capsys.readouterr().err


def test_main_serves_forwards_sigterm_and_restores_signal_handler(monkeypatch):
    import pvm_control_engine.bootstrap as bootstrap

    signals = []
    old_handler = object()
    installed_handler = None

    class Server:
        shutdown_requested = False

        def request_shutdown(self):
            self.shutdown_requested = True

    class Runtime:
        server = Server()
        closed = False

        def serve(self):
            installed_handler(15, None)

        def close(self):
            self.closed = True

    runtime = Runtime()
    monkeypatch.setattr(bootstrap, "load_settings", lambda: load_settings({}))
    monkeypatch.setattr(bootstrap, "build_runtime", lambda *_a, **_k: runtime)
    monkeypatch.setattr(bootstrap.signal, "getsignal", lambda _sig: old_handler)

    def set_signal(_sig, handler):
        nonlocal installed_handler
        signals.append(handler)
        if handler is not old_handler:
            installed_handler = handler
        return old_handler

    monkeypatch.setattr(bootstrap.signal, "signal", set_signal)
    assert main(["serve"]) == 0
    assert runtime.server.shutdown_requested
    assert runtime.closed
    assert signals[-1] is old_handler


def test_main_signal_setup_failure_still_closes_runtime(monkeypatch):
    import pvm_control_engine.bootstrap as bootstrap

    class Runtime:
        server = type("Server", (), {"request_shutdown": lambda self: None})()
        closed = False

        def serve(self):
            raise AssertionError("serve must not start if signal setup failed")

        def close(self):
            self.closed = True

    runtime = Runtime()
    monkeypatch.setattr(bootstrap, "load_settings", lambda: load_settings({}))
    monkeypatch.setattr(bootstrap, "build_runtime", lambda *_a, **_k: runtime)
    monkeypatch.setattr(bootstrap.signal, "getsignal", lambda _sig: None)
    monkeypatch.setattr(
        bootstrap.signal,
        "signal",
        lambda *_a: (_ for _ in ()).throw(ValueError("signal setup failed")),
    )
    with pytest.raises(ValueError, match="signal setup failed"):
        main(["serve"])
    assert runtime.closed


@pytest.mark.parametrize(
    ("serve_error", "expected_code", "expected_message"),
    [(KeyboardInterrupt(), 130, None), (OSError("private detail"), 1, "OSError")],
)
def test_main_serving_errors_preserve_exit_and_cleanup(
    monkeypatch, capsys, serve_error, expected_code, expected_message
):
    import pvm_control_engine.bootstrap as bootstrap

    class Runtime:
        server = type("Server", (), {"request_shutdown": lambda self: None})()
        closed = False

        def serve(self):
            raise serve_error

        def close(self):
            self.closed = True

    runtime = Runtime()
    monkeypatch.setattr(bootstrap, "load_settings", lambda: load_settings({}))
    monkeypatch.setattr(bootstrap, "build_runtime", lambda *_a, **_k: runtime)
    monkeypatch.setattr(bootstrap.signal, "getsignal", lambda _sig: None)
    monkeypatch.setattr(bootstrap.signal, "signal", lambda *_a: None)
    assert main(["serve"]) == expected_code
    assert runtime.closed
    stderr = capsys.readouterr().err
    if expected_message:
        assert expected_message in stderr
        assert "private detail" not in stderr


def test_rpc_methods_work_over_private_unix_socket_and_shutdown_cleans_socket(tmp_path):
    service = FakeService()
    path, server, thread = start_server(tmp_path, service)
    assert path.stat().st_mode & 0o777 == 0o600
    assert (
        rpc(path, {"jsonrpc": "2.0", "id": 1, "method": "engine.health", "params": {}})["result"][
            "status"
        ]
        == "ok"
    )
    assert (
        rpc(path, {"jsonrpc": "2.0", "id": "v", "method": "vm.get", "params": {"uuid": UUID}})[
            "result"
        ]["uuid"]
        == UUID
    )
    assert rpc(path, {"jsonrpc": "2.0", "id": 2, "method": "vm.list"})["result"] == {"value": []}
    assert (
        rpc(
            path,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "vm.operate",
                "params": {"uuid": UUID, "action": "stop"},
            },
        )["result"]["state"]
        == "OUTCOME_UNKNOWN"
    )
    server.close()
    thread.join(timeout=3)
    assert not thread.is_alive()
    assert not path.exists()


def test_rpc_worker_count_is_bounded_and_busy_requests_are_rejected(tmp_path):
    started = threading.Event()
    release = threading.Event()

    class BlockingService(FakeService):
        def list_vms(self):
            started.set()
            release.wait(timeout=3)
            return {"value": []}

    path, server, thread = start_server(tmp_path, BlockingService(), max_workers=1)
    result = {}
    first = threading.Thread(
        target=lambda: result.setdefault(
            "first", rpc(path, {"jsonrpc": "2.0", "id": 1, "method": "vm.list"})
        )
    )
    first.start()
    assert started.wait(timeout=2)
    try:
        busy = rpc(path, {"jsonrpc": "2.0", "id": 2, "method": "engine.health"})
        assert busy["error"]["code"] == -32002
    finally:
        release.set()
        first.join(timeout=3)
        server.close()
        thread.join(timeout=3)
    assert result["first"]["result"] == {"value": []}
    assert not first.is_alive() and not thread.is_alive()


def test_permitted_read_and_session_methods_are_available_over_socket(tmp_path):
    path, server, thread = start_server(tmp_path, FakeService())
    try:
        cases = (
            ("host.status", {}, "current"),
            ("host.metrics", {}, "current"),
            ("host.local", {}, "current"),
            ("network.nic_samples", {}, "physical_nics"),
            ("audit.recent", {"limit": 25}, "entries"),
            ("desktop.list", {}, "current"),
            ("desktop.operate", {"action": "stop", "uuids": [UUID]}, "action"),
            ("overview.dashboard", {}, "current"),
            ("vm.tap_mapping", {}, "current"),
            ("network.nic_list", {}, "current"),
            ("session.logout", {}, False),
        )
        for request_id, (method, params, expected) in enumerate(cases, 10):
            response = rpc(
                path, {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
            )
            assert response["result"]
            result = response["result"]
            if method == "session.logout":
                assert result["authenticated"] is expected
            elif method == "network.nic_samples":
                assert result["physical_nics"]["status"] == "current"
            elif method == "audit.recent":
                assert result[expected] == []
            elif method == "desktop.operate":
                assert result[expected] == "stop"
            else:
                assert result["status"] == expected
    finally:
        server.close()
        thread.join(timeout=3)


def test_unknown_rpc_methods_and_unknown_fields_are_rejected(tmp_path):
    path, server, thread = start_server(tmp_path, FakeService())
    try:
        unknown = rpc(
            path, {"jsonrpc": "2.0", "id": 1, "method": "user.raw_xml", "params": {"xml": "<x/>"}}
        )
        assert unknown["error"]["code"] == -32601
        fields = rpc(
            path,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "vm.get",
                "params": {"uuid": UUID, "query": "arbitrary"},
            },
        )
        assert fields["error"]["code"] == -32602
        top_level = rpc(path, {"jsonrpc": "2.0", "id": 3, "method": "engine.health", "extra": True})
        assert top_level["error"]["code"] == -32600
    finally:
        server.close()
        thread.join(timeout=3)


def test_unauthorized_peer_uid_is_rejected_before_method_execution(tmp_path):
    service = FakeService()
    path, server, thread = start_server(tmp_path, service, allowed_uids={os.getuid() + 1})
    try:
        response = rpc(path, {"jsonrpc": "2.0", "id": 7, "method": "engine.health", "params": {}})
        assert response["error"]["code"] == -32001
        assert service.calls == []
    finally:
        server.close()
        thread.join(timeout=3)


def test_canonical_adapter_uses_exact_explicit_sbell_commands_and_xml():
    class Runner:
        def __init__(self):
            self.calls = []

        def run(self, argv, *, timeout=None):
            self.calls.append(tuple(argv))
            payload = (
                "<description>synthetic-token</description>"
                if argv[2] == "login"
                else "<description/>"
            )
            xml = f"<response><status>success</status>{payload}</response>"
            return ProcessResult(0, xml, "", False, False, 0.001)

    runner = Runner()
    adapter = LocalPvmAdapter(
        SbellClient(("sbell",), runner, allow_credential_argv=True),
        runner,
        ("pvm-running-vms",),
        allow_credential_argv=True,
    )
    adapter.login("operator", "synthetic-password")
    adapter.validate_session(PvmSession("operator", "synthetic-token"))
    adapter.logout(PvmSession("operator", "synthetic-token"))
    adapter.list_objects("synthetic-token")
    adapter.list_desktops("synthetic-token")
    adapter.vm_detail("synthetic-token", UUID)
    adapter.tap_mapping("synthetic-token")
    adapter.dashboard("synthetic-token")
    adapter.host_status("synthetic-token")
    adapter.host_metrics("synthetic-token")
    adapter.physical_nics("synthetic-token")

    actual = [(call[1], call[2], call[3]) for call in runner.calls]
    expected = [
        (
            "user",
            "login",
            "<params><username>operator</username><password>synthetic-password</password></params>",
        ),
        ("user", "whoami", "<params/>"),
        ("user", "logout", "<params/>"),
        ("user", "objects", VM_QUERY),
        ("user", "objects", DESKTOP_QUERY),
        (
            "user",
            "objects",
            f"<params><query>/objects/object/pvm_vmm_obj[uuid[text()='{UUID}']]</query></params>",
        ),
        ("user", "objects", VM_QUERY),
        ("user", "objects", DASHBOARD_QUERY),
        ("sball", "show", "<params/>"),
        ("monitoring", "metrics", "<params/>"),
        ("network", "nic-list", "<params/>"),
    ]
    assert actual == expected
    assert all(call[-1] == "synthetic-token" for call in runner.calls[1:])


def test_sbell_errors_for_malformed_incomplete_and_empty_responses_are_safe():
    class Runner:
        def __init__(self, output):
            self.output = output

        def run(self, argv, *, timeout=None):
            return ProcessResult(0, self.output, "", False, False, 0.001)

    for output, expected in (
        ("<response><description>synthetic-secret</description>", "SBELL_INVALID_XML"),
        (
            "<response><description>synthetic-secret</description></response>",
            "SBELL_STATUS_MISSING",
        ),
        ("", "SBELL_NO_RESPONSE"),
    ):
        client = SbellClient(("sbell",), Runner(output))
        with pytest.raises(AppError) as error:
            client.call("user", "whoami")
        assert error.value.code == expected
        assert "synthetic-secret" not in str(error.value)
        assert "synthetic-secret" not in repr(error.value)


def test_sbell_client_enforces_token_gate_and_maps_process_timeout():
    from pvm_control_engine.domain.models import ErrorKind
    from pvm_control_engine.infrastructure.process import ProcessTimeout

    class Runner:
        def __init__(self, result=None, error=None):
            self.calls = []
            self.result = result
            self.error = error

        def run(self, argv, *, timeout=None):
            self.calls.append((tuple(argv), timeout))
            if self.error is not None:
                raise self.error
            return self.result

    denied_runner = Runner()
    denied = SbellClient(("sbell",), denied_runner)
    with pytest.raises(AppError) as gated:
        denied.call("vm", "start", "<vm_key>x</vm_key>", "secret-token")
    assert gated.value.kind is ErrorKind.POLICY
    assert gated.value.code == "CREDENTIAL_ARGV_ACK_REQUIRED"
    assert denied_runner.calls == []

    timeout_runner = Runner(error=ProcessTimeout(reaped=True))
    allowed = SbellClient(("sbell",), timeout_runner, allow_credential_argv=True)
    with pytest.raises(AppError) as timed_out:
        allowed.call("vm", "start", "<vm_key>x</vm_key>", "secret-token", timeout=4.0)
    assert timed_out.value.code == "PVM_COMMAND_TIMEOUT"
    assert timeout_runner.calls == [
        (("sbell", "vm", "start", "<vm_key>x</vm_key>", "secret-token"), 4.0)
    ]
    assert "secret-token" not in str(timed_out.value)


def test_rpc_framing_rejects_invalid_utf8_and_oversized_frame(tmp_path):
    service = FakeService()
    path, server, thread = start_server(tmp_path, service, max_message_bytes=1024)
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(str(path))
        client.sendall(b"\xff\n")
        assert json.loads(client.recv(4096))["error"]["code"] == -32700
        client.close()
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(str(path))
        client.sendall(b"x" * 1025)
        assert json.loads(client.recv(4096))["error"]["code"] == -32700
        client.close()
    finally:
        server.close()
        thread.join(timeout=3)


def test_objects_command_accepts_only_known_query_inputs():
    class App:
        def inventory(self, token):
            return (None, "inventory-section")

    class Auth:
        def token(self):
            return "fake-token"

    command = UserObjects(App(), Auth())
    assert command.execute("vm_inventory") == "inventory-section"
    with pytest.raises(ValueError, match="unsupported"):
        command.execute("<query>arbitrary</query>")


def test_engine_service_dispatches_only_registered_vm_actions():
    from pvm_control_engine.domain.models import Action
    from pvm_control_engine.infrastructure.sbell.commands.registry import CommandRegistry

    class Store:
        def load(self):
            return PvmSession("operator", "secret-token")

        def clear(self):
            pass

    class Auth:
        def stored_session(self):
            return Store().load()

        def session(self):
            return Store().load()

    class Command:
        def __init__(self):
            self.calls = []

        def execute(self, uuid):
            self.calls.append(uuid)
            return {"state": "SUCCEEDED"}

        def execute_many(self, uuids):
            self.calls.append(uuids)
            return {"state": "SUCCEEDED"}

    command = Command()
    registry = CommandRegistry(
        {"desktop.operate": object()},
        {action: command for action in Action},
    )
    service = EngineService(application=object(), auth=Auth(), registry=registry)
    with pytest.raises(AppError) as invalid_action:
        service.operate("poweroff", UUID)
    assert invalid_action.value.code == "INVALID_ACTION"
    assert command.calls == []
    assert service.operate("stop", UUID) == {"state": "SUCCEEDED"}
    assert command.calls == [UUID]


def test_rpc_rejects_passwords_and_login_is_not_an_ipc_method(capsys):
    service = FakeService()
    result = RpcDispatcher(service).handle(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "session.login",
            "params": {"username": "operator", "password": "private-password"},
        }
    )
    assert result["error"]["code"] == -32601
    assert "private-password" not in json.dumps(result)
    assert service.calls == []
    assert capsys.readouterr().out == ""
    assert capsys.readouterr().err == ""


def test_rpc_notifications_are_rejected():
    service = FakeService()
    dispatcher = RpcDispatcher(service)
    notification = dispatcher.handle(
        {"jsonrpc": "2.0", "method": "vm.operate", "params": {"uuid": UUID, "action": "start"}}
    )
    assert notification["error"]["code"] == -32600
