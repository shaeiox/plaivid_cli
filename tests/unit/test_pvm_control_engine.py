from __future__ import annotations

import argparse
import json
import os
import socket
import threading
import time
from pathlib import Path

import pytest

from plaivid_cli.config import load_settings
from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import Action, PvmSession
from plaivid_cli.infrastructure.process import ProcessResult
from plaivid_cli.infrastructure.pvm.adapter.local import LocalPvmAdapter
from plaivid_cli.infrastructure.pvm.adapter.requests import DASHBOARD_QUERY, DESKTOP_QUERY, VM_QUERY
from plaivid_cli.infrastructure.pvm.sbell import SbellClient
from pvm_control_engine.application.service import EngineService
from pvm_control_engine.bootstrap import _parse_socket_mode, build_runtime
from pvm_control_engine.infrastructure.sbell.commands.user.objects import UserObjects
from pvm_control_engine.ipc.dispatcher import RpcDispatcher
from pvm_control_engine.ipc.server import UnixRpcServer

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

    def desktop_list(self):
        return {"status": "current", "value": []}

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

    def operate(self, action, uuid):
        self.calls.append((action, uuid))
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


def test_socket_mode_configuration_is_octal_and_restrictive():
    assert _parse_socket_mode("0600") == 0o600
    assert _parse_socket_mode("0660") == 0o660
    with pytest.raises(argparse.ArgumentTypeError, match="0600 or 0660"):
        _parse_socket_mode("0666")


def test_engine_composition_registers_each_permitted_vm_action_without_starting_pvm(tmp_path):
    settings = load_settings({"PLAIVID_STATE_DIR": str(tmp_path / "state")})
    runtime = build_runtime(settings, tmp_path / "engine.sock")
    try:
        assert set(runtime.service.vm_operations) == {
            "start",
            "stop",
            "kill",
            "reset",
            "pause",
            "resume",
        }
    finally:
        runtime.close()
    assert not (tmp_path / "engine.sock").exists()


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
            ("desktop.list", {}, "current"),
            ("overview.dashboard", {}, "current"),
            ("vm.tap_mapping", {}, "current"),
            ("network.nic_list", {}, "current"),
            ("session.login", {"username": "operator", "password": "private"}, "operator"),
            ("session.logout", {}, False),
        )
        for request_id, (method, params, expected) in enumerate(cases, 10):
            response = rpc(
                path, {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
            )
            assert response["result"]
            result = response["result"]
            if method == "session.login":
                assert result["username"] == expected
                assert "token" not in result and "private" not in json.dumps(result)
            elif method == "session.logout":
                assert result["authenticated"] is expected
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
        SbellClient(("sbell",), runner), runner, ("pvm-running-vms",), allow_credential_argv=True
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
    for action in Action:
        adapter.dispatch_action("synthetic-token", action, UUID)

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
    expected.extend(
        (
            "vm",
            action.value,
            f"<vm_key>{UUID}</vm_key>"
            if action is not Action.START
            else f"<vm_start><vm_key>{UUID}</vm_key><host>auto</host><version_start><version_enable>no</version_enable><version_vkey></version_vkey></version_start><exit_from_replicate>yes</exit_from_replicate></vm_start>",
        )
        for action in Action
    )
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

    command = UserObjects(App())
    assert command.execute("fake-token", "vm_inventory") == "inventory-section"
    with pytest.raises(ValueError, match="unsupported"):
        command.execute("fake-token", "<query>arbitrary</query>")


def test_engine_service_rejects_noncanonical_uuid_and_unknown_action_without_dispatch(tmp_path):
    class Store:
        def load(self):
            return PvmSession("operator", "secret-token")

        def clear(self):
            pass

    class Whoami:
        def execute(self, session):
            return True

    class Command:
        def __init__(self):
            self.calls = []

        def execute(self, token, uuid):
            self.calls.append((token, uuid))
            return {"state": "SUCCEEDED"}

    command = Command()
    service = EngineService(
        application=object(),
        sessions=object(),
        session_store=Store(),
        provider=object(),
        commands={"user.whoami": Whoami(), "vm.stop": command},
    )
    with pytest.raises(AppError) as invalid_uuid:
        service.operate("stop", UUID.upper())
    assert invalid_uuid.value.code == "INVALID_UUID"
    with pytest.raises(AppError) as invalid_action:
        service.operate("poweroff", UUID)
    assert invalid_action.value.code == "INVALID_ACTION"
    assert command.calls == []
    assert service.operate("stop", UUID) == {"state": "SUCCEEDED"}
    assert command.calls == [("secret-token", UUID)]


def test_login_rpc_never_returns_or_prints_password_or_token(capsys):
    service = FakeService()
    result = RpcDispatcher(service).handle(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "session.login",
            "params": {"username": "operator", "password": "private-password"},
        }
    )
    assert result["result"] == {"username": "operator"}
    assert "private-password" not in json.dumps(result)
    assert "secret-token" not in json.dumps(result)
    assert capsys.readouterr().out == ""
    assert capsys.readouterr().err == ""


def test_rpc_login_requires_exact_fields_and_no_notifications():
    service = FakeService()
    dispatcher = RpcDispatcher(service)
    missing = dispatcher.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "session.login", "params": {"username": "x"}}
    )
    assert missing["error"]["code"] == -32602
    notification = dispatcher.handle(
        {"jsonrpc": "2.0", "method": "vm.operate", "params": {"uuid": UUID, "action": "start"}}
    )
    assert notification["error"]["code"] == -32600
