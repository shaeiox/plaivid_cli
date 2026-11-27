"""Small synchronous JSON-RPC client for the local Engine socket."""

from __future__ import annotations

import json
import os
import socket
import uuid
from pathlib import Path
from typing import Any

MAX_FRAME_BYTES = 1_048_576


class EngineRpcError(RuntimeError):
    def __init__(self, code: int, message: str, data: dict[str, Any] | None = None) -> None:
        self.code = code
        self.data = data or {}
        super().__init__(message)


class EngineClient:
    """One request per AF_UNIX connection; never accepts PVM tokens or raw commands."""

    def __init__(self, socket_path: str | Path | None = None, *, timeout: float = 35.0) -> None:
        configured = socket_path or os.environ.get("PLAIVID_CONTROL_SOCKET")
        if configured is None:
            runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
            state_dir = os.environ.get(
                "PLAIVID_STATE_DIR", str(Path.home() / ".local/state/plaivid")
            )
            configured = (
                str(Path(runtime_dir) / "pvm-control-engine.sock")
                if runtime_dir
                else str(Path(state_dir) / "pvm-control-engine.sock")
            )
        self.socket_path = str(Path(configured).expanduser())
        self.timeout = timeout

    def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        if not isinstance(method, str) or not method or not isinstance(params or {}, dict):
            raise ValueError("invalid RPC request")
        request = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params or {},
        }
        frame = (
            json.dumps(request, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode(
                "utf-8"
            )
            + b"\n"
        )
        if len(frame) > MAX_FRAME_BYTES:
            raise ValueError("RPC request exceeds the message limit")
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(self.timeout)
        try:
            client.connect(self.socket_path)
            client.sendall(frame)
            response = self._read_response(client)
        except OSError as exc:
            raise EngineRpcError(-32010, "PVM Control Engine is unavailable") from exc
        finally:
            client.close()
        if not isinstance(response, dict) or response.get("jsonrpc") != "2.0":
            raise EngineRpcError(-32603, "Invalid Engine response")
        if response.get("id") != request["id"]:
            raise EngineRpcError(-32603, "Mismatched Engine response ID")
        if "error" in response:
            error = response["error"]
            if (
                not isinstance(error, dict)
                or not isinstance(error.get("code"), int)
                or not isinstance(error.get("message"), str)
            ):
                raise EngineRpcError(-32603, "Malformed Engine error")
            raise EngineRpcError(error["code"], error["message"], error.get("data"))
        if "result" not in response:
            raise EngineRpcError(-32603, "Engine response has no result")
        return response["result"]

    @staticmethod
    def _read_response(client: socket.socket) -> dict[str, Any]:
        data = bytearray()
        while True:
            part = client.recv(min(4096, MAX_FRAME_BYTES + 1 - len(data)))
            if not part:
                raise EngineRpcError(-32603, "Incomplete Engine response")
            newline = part.find(b"\n")
            if newline >= 0:
                if newline != len(part) - 1:
                    raise EngineRpcError(-32603, "Invalid Engine response framing")
                data.extend(part[:newline])
                break
            data.extend(part)
            if len(data) > MAX_FRAME_BYTES:
                raise EngineRpcError(-32603, "Engine response exceeds the message limit")
        try:
            response = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise EngineRpcError(-32603, "Invalid Engine response JSON") from None
        if not isinstance(response, dict):
            raise EngineRpcError(-32603, "Invalid Engine response JSON")
        return response
