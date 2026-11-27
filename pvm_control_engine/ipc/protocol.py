"""Strict JSON-RPC 2.0 validation and safe error envelopes."""

from __future__ import annotations

import json
from typing import Any

MAX_MESSAGE_BYTES = 1_048_576


class RpcFault(Exception):
    def __init__(self, code: int, message: str, data: dict[str, Any] | None = None) -> None:
        self.code, self.message, self.data = code, message, data
        super().__init__(message)


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def _reject_constant(_value):
    raise ValueError("non-standard JSON constant")


def parse_request(raw: bytes) -> dict[str, Any]:
    try:
        request = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
        raise RpcFault(-32700, "Parse error") from None
    if not isinstance(request, dict):
        raise RpcFault(-32600, "Invalid Request")
    if set(request) - {"jsonrpc", "method", "params", "id"}:
        raise RpcFault(-32600, "Invalid Request")
    if request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
        raise RpcFault(-32600, "Invalid Request")
    request_id = request.get("id")
    if "id" in request and (
        isinstance(request_id, bool) or not isinstance(request_id, (str, int, type(None)))
    ):
        raise RpcFault(-32600, "Invalid Request")
    if not isinstance(request.get("params", {}), dict):
        raise RpcFault(-32600, "Invalid Request")
    return request


def success(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def failure(
    request_id: Any, code: int, message: str, data: dict[str, Any] | None = None
) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}
