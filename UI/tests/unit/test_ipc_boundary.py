from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path

import pytest
from plaivid_ui.engine_client.client import EngineClient
from plaivid_ui.engine_client.dto import Action, ObjectVM, VMRecord
from plaivid_ui.engine_client.gateway import EngineGateway
from plaivid_ui.presentation.tui.app import PlaividTui

UI_ROOT = Path(__file__).parents[2]
SRC = UI_ROOT / "tui" / "src" / "plaivid_ui"


class FakeSocket:
    def __init__(self):
        self.sent = b""
        self.closed = False
        self.response = b""

    def settimeout(self, timeout):
        self.timeout = timeout

    def connect(self, path):
        self.path = path

    def sendall(self, data):
        self.sent += data
        request = json.loads(data)
        self.response = json.dumps({
            "jsonrpc": "2.0", "id": request["id"], "result": {"status": "ok"}
        }).encode() + b"\n"

    def recv(self, size):
        result, self.response = self.response, b""
        return result

    def close(self):
        self.closed = True


def test_engine_client_uses_single_local_json_rpc_frame(monkeypatch, tmp_path):
    fake = FakeSocket()
    monkeypatch.setattr("plaivid_ui.engine_client.client.socket.socket", lambda *args: fake)
    socket_path = tmp_path / "engine.sock"
    client = EngineClient(socket_path, timeout=2)

    assert client.call("engine.health") == {"status": "ok"}
    request = json.loads(fake.sent)
    assert request["jsonrpc"] == "2.0"
    assert request["method"] == "engine.health"
    assert request["params"] == {}
    assert fake.path == str(socket_path)
    assert fake.closed


def test_engine_client_rejects_arbitrary_python_parameters():
    client = EngineClient("/tmp/not-used.sock")
    with pytest.raises(ValueError, match="invalid RPC request"):
        client.call("vm.list", ["not", "an", "object"])


def test_gateway_maps_ui_operations_only_to_allowlisted_engine_methods():
    class RecordingClient:
        def __init__(self):
            self.calls = []

        def call(self, method, params=None):
            self.calls.append((method, params or {}))
            if method == "vm.operate":
                return {"operation_id": "op-1", "action": "stop", "state": "OUTCOME_UNKNOWN", "targets": [], "started_at": "2026-11-27T00:00:00+00:00"}
            if method == "snapshot.collect":
                return {"generation": 1, "sections": {"inventory": {"status": "current", "value": {"objects": [], "records": []}}}}
            return {"status": "ok", "value": []}

    client = RecordingClient()
    gateway = EngineGateway(client)
    gateway.connect()
    gateway.refresh(sections=("inventory",))
    gateway.execute(Action.STOP, (VMRecord(ObjectVM(uuid="481e458c-c6ba-4fe7-88f6-26a59e416568", name="alpha")),), None, is_bulk=False)
    gateway.logout()

    assert [method for method, _ in client.calls] == [
        "engine.health", "vm.list", "snapshot.collect", "vm.operate", "session.logout"
    ]
    assert client.calls[2][1] == {"sections": ["inventory"]}
    assert client.calls[3][1] == {
        "action": "stop", "uuid": "481e458c-c6ba-4fe7-88f6-26a59e416568"
    }
    assert all("token" not in params and "password" not in params for _, params in client.calls)


def test_ui_source_has_no_engine_or_legacy_runtime_imports_or_process_execution():
    forbidden_modules = {"pvm_control_engine", "plaivid_cli", "subprocess"}
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            else:
                modules = []
            assert all(module.split(".", 1)[0] not in forbidden_modules for module in modules), path
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {"system", "popen", "Popen", "create_subprocess_exec", "create_subprocess_shell"}, path
        source = path.read_text(encoding="utf-8")
        assert "subprocess.run" not in source, path


def test_tui_mounts_safely_when_engine_socket_is_unavailable(tmp_path):
    async def exercise():
        app = PlaividTui(EngineClient(tmp_path / "missing-engine.sock"))
        async with app.run_test() as pilot:
            await pilot.pause(0.2)
            assert app.session is None
            assert "pvm-control-engine login" in str(app.query_one("#login-error").render())

    asyncio.run(exercise())


def test_ui_distribution_is_independently_discoverable():
    config = (UI_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "plaivid-ui"' in config
    assert 'plaivid = "plaivid_ui.engine_client.cli:main"' in config
    assert 'include = ["plaivid_ui*"]' in config
