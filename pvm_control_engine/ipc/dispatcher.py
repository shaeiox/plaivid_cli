"""Allowlisted versioned JSON-RPC methods over the local socket."""

from __future__ import annotations

from typing import Any

from pvm_control_engine.domain.errors import AppError

from .protocol import RpcFault, failure, success

METHODS = {
    "engine.health": (set(), set()),
    "overview.dashboard": (set(), set()),
    "snapshot.collect": ({"sections"}, {"sections"}),
    "vm.list": (set(), set()),
    "vm.get": ({"uuid"}, {"uuid"}),
    "host.status": (set(), set()),
    "host.metrics": (set(), set()),
    "host.local": (set(), set()),
    "network.nic_list": (set(), set()),
    "network.nic_samples": (set(), set()),
    "desktop.list": (set(), set()),
    "audit.recent": ({"limit"}, set()),
    "vm.tap_mapping": (set(), set()),
    "session.logout": (set(), set()),
    "vm.operate": ({"uuid", "uuids", "action"}, {"action"}),
    "desktop.operate": ({"action", "uuids"}, {"action", "uuids"}),
}


class RpcDispatcher:
    def __init__(self, service) -> None:
        self.service = service

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        request_id = request.get("id")
        method = request.get("method")
        if not isinstance(method, str) or method not in METHODS:
            return failure(request_id, -32601, "Method not found")
        allowed, required = METHODS[method]
        params = request.get("params", {})
        if not isinstance(params, dict) or set(params) - allowed or not required.issubset(params):
            return failure(request_id, -32602, "Invalid params")
        if "id" not in request:
            return failure(None, -32600, "Invalid Request")
        if method == "vm.operate" and (("uuid" in params) == ("uuids" in params)):
            return failure(request_id, -32602, "Provide exactly one uuid or uuids parameter")
        try:
            if method == "engine.health":
                result = {"status": "ok", "service": "pvm-control-engine", "contract": "plaivid.engine.v1"}
            elif method == "overview.dashboard":
                result = self.service.dashboard()
            elif method == "snapshot.collect":
                sections = params["sections"]
                if not isinstance(sections, list) or any(not isinstance(item, str) for item in sections):
                    raise RpcFault(-32602, "Invalid params")
                result = self.service.snapshot(tuple(sections))
            elif method == "vm.list":
                result = self.service.list_vms()
            elif method == "vm.get":
                _require_text(params, "uuid")
                result = self.service.vm_detail(params["uuid"])
            elif method == "host.status":
                result = self.service.host_status()
            elif method == "host.metrics":
                result = self.service.host_metrics()
            elif method == "host.local":
                result = self.service.local_host()
            elif method == "network.nic_list":
                result = self.service.nic_list()
            elif method == "network.nic_samples":
                result = self.service.nic_samples()
            elif method == "desktop.list":
                result = self.service.desktop_list()
            elif method == "audit.recent":
                limit = params.get("limit", 100)
                if isinstance(limit, bool) or not isinstance(limit, int):
                    raise RpcFault(-32602, "Invalid params")
                result = self.service.recent_audit(limit)
            elif method == "vm.tap_mapping":
                result = self.service.tap_mapping()
            elif method == "session.logout":
                result = self.service.logout()
            elif method == "vm.operate":
                _require_text(params, "action")
                if "uuid" in params:
                    _require_text(params, "uuid")
                    result = self.service.operate(params["action"], uuid=params["uuid"])
                else:
                    result = self.service.operate(params["action"], uuids=_require_uuid_list(params))
            else:
                _require_text(params, "action")
                result = self.service.operate_desktop(params["action"], _require_uuid_list(params))
            return success(request_id, result)
        except RpcFault as exc:
            return failure(request_id, exc.code, exc.message, exc.data)
        except AppError as exc:
            data = {"code": exc.code, "kind": exc.kind.value}
            message = str(exc)
            if any(secret in message.casefold() for secret in ("password", "token", "argv", "sballd")):
                message = "Engine request failed"
            return failure(request_id, -32000, message, data)
        except (ValueError, TypeError):
            return failure(request_id, -32602, "Invalid params")
        except Exception:
            return failure(request_id, -32603, "Internal engine error")


def _require_uuid_list(params: dict[str, Any]) -> tuple[str, ...]:
    values = params.get("uuids")
    if not isinstance(values, list) or not values or len(values) > 100:
        raise RpcFault(-32602, "Invalid params")
    if any(not isinstance(value, str) or not value for value in values):
        raise RpcFault(-32602, "Invalid params")
    return tuple(values)


def _require_text(params: dict[str, Any], name: str) -> None:
    value = params.get(name)
    if not isinstance(value, str) or not value.strip():
        raise RpcFault(-32602, "Invalid params")
