"""Allowlisted JSON-RPC methods; no caller-supplied XML or process arguments."""

from __future__ import annotations

from typing import Any

from plaivid_cli.domain.errors import AppError

from .protocol import RpcFault, failure, success

_METHODS = {
    "engine.health": (set(), set()),
    "vm.list": (set(), set()),
    "vm.get": ({"uuid"}, {"uuid"}),
    "host.status": (set(), set()),
    "host.metrics": (set(), set()),
    "desktop.list": (set(), set()),
    "overview.dashboard": (set(), set()),
    "vm.tap_mapping": (set(), set()),
    "network.nic_list": (set(), set()),
    "session.login": ({"username", "password"}, {"username", "password"}),
    "session.logout": (set(), set()),
    "vm.operate": ({"uuid", "action"}, {"uuid", "action"}),
}


class RpcDispatcher:
    def __init__(self, service) -> None:
        self.service = service

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        request_id = request.get("id")
        method = request["method"]
        if method not in _METHODS:
            return failure(request_id, -32601, "Method not found")
        allowed, required = _METHODS[method]
        params = request.get("params", {})
        if set(params) - allowed or not required.issubset(params):
            return failure(request_id, -32602, "Invalid params")
        if "id" not in request:
            # Notifications are intentionally unsupported; operations must have a result handle.
            return failure(None, -32600, "Invalid Request")
        try:
            if method == "engine.health":
                result = {"status": "ok", "service": "pvm-control-engine"}
            elif method == "vm.list":
                result = self.service.list_vms()
            elif method == "vm.get":
                _require_text(params, "uuid")
                result = self.service.vm_detail(params["uuid"])
            elif method == "host.status":
                result = self.service.host_status()
            elif method == "host.metrics":
                result = self.service.host_metrics()
            elif method == "desktop.list":
                result = self.service.desktop_list()
            elif method == "overview.dashboard":
                result = self.service.dashboard()
            elif method == "vm.tap_mapping":
                result = self.service.tap_mapping()
            elif method == "network.nic_list":
                result = self.service.nic_list()
            elif method == "session.login":
                _require_text(params, "username")
                _require_text(params, "password")
                result = self.service.login(params["username"], params["password"])
            elif method == "session.logout":
                result = self.service.logout()
            else:
                _require_text(params, "uuid")
                _require_text(params, "action")
                result = self.service.operate(params["action"], params["uuid"])
            return success(request_id, result)
        except RpcFault as exc:
            return failure(request_id, exc.code, exc.message, exc.data)
        except AppError as exc:
            return failure(request_id, -32000, str(exc), {"code": exc.code, "kind": exc.kind.value})
        except (ValueError, TypeError):
            return failure(request_id, -32602, "Invalid params")
        except Exception:
            # Never return exception strings, traceback, argv, or response XML to a client.
            return failure(request_id, -32603, "Internal engine error")


def _require_text(params: dict[str, Any], name: str) -> None:
    value = params.get(name)
    if not isinstance(value, str) or not value or (name != "password" and not value.strip()):
        raise RpcFault(-32602, "Invalid params")
