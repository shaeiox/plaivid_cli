"""Bounded JSON-RPC server over a private Unix-domain stream socket."""

from __future__ import annotations

import errno
import json
import os
import socket
import stat
import struct
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .dispatcher import RpcDispatcher
from .protocol import MAX_MESSAGE_BYTES, RpcFault, failure, parse_request


class UnixRpcServer:
    def __init__(
        self,
        path: str | Path,
        dispatcher: RpcDispatcher,
        *,
        allowed_uids=None,
        max_workers: int = 4,
        max_message_bytes: int = MAX_MESSAGE_BYTES,
        socket_mode: int = 0o600,
    ) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be positive")
        if not 1024 <= max_message_bytes <= MAX_MESSAGE_BYTES:
            raise ValueError("max_message_bytes must be between 1024 and the protocol maximum")
        if socket_mode not in {0o600, 0o660}:
            raise ValueError("socket_mode must be 0600 or 0660")
        self.socket_mode = socket_mode
        self.path = Path(path).expanduser().absolute()
        self.dispatcher = dispatcher
        self.allowed_uids = frozenset({os.getuid()} if allowed_uids is None else allowed_uids)
        self.max_workers = max_workers
        self.max_message_bytes = max_message_bytes
        self._listener: socket.socket | None = None
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="pvm-engine-rpc"
        )
        self._slots = threading.BoundedSemaphore(max_workers)
        self._stop = threading.Event()
        self._socket_identity: tuple[int, int] | None = None

    def serve_forever(self) -> None:
        self._bind()
        listener = self._listener
        assert listener is not None
        try:
            while not self._stop.is_set():
                try:
                    conn, _ = listener.accept()
                except TimeoutError:
                    continue
                except OSError:
                    if self._stop.is_set():
                        break
                    raise
                conn.settimeout(5.0)
                if not self._slots.acquire(blocking=False):
                    self._send(conn, failure(None, -32002, "Engine is busy"))
                    conn.close()
                    continue
                try:
                    future = self._executor.submit(self._serve_connection, conn)
                except RuntimeError:
                    self._slots.release()
                    self._send(conn, failure(None, -32002, "Engine is shutting down"))
                    conn.close()
                    continue
                future.add_done_callback(lambda _future: self._slots.release())
        finally:
            self.close()

    def request_shutdown(self) -> None:
        """Ask the accept loop to stop; it will drain workers and unlink its socket."""
        self._stop.set()

    def _bind(self) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._remove_stale_socket()
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        bound = False
        try:
            listener.bind(str(self.path))
            bound = True
            metadata = self.path.stat(follow_symlinks=False)
            self._socket_identity = (metadata.st_dev, metadata.st_ino)
            os.chmod(self.path, self.socket_mode)
            listener.listen(self.max_workers)
            listener.settimeout(0.2)
        except Exception:
            listener.close()
            if bound and self._socket_identity is not None:
                try:
                    metadata = self.path.stat(follow_symlinks=False)
                    if (metadata.st_dev, metadata.st_ino) == self._socket_identity:
                        self.path.unlink()
                except FileNotFoundError:
                    pass
                self._socket_identity = None
            raise
        self._listener = listener

    def _remove_stale_socket(self) -> None:
        try:
            metadata = self.path.stat(follow_symlinks=False)
        except FileNotFoundError:
            return
        if not stat.S_ISSOCK(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise RuntimeError("socket path exists and is not an owned socket")
        probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            probe.settimeout(0.2)
            probe.connect(str(self.path))
        except OSError as exc:
            if exc.errno != errno.ECONNREFUSED:
                raise RuntimeError("could not verify an existing socket path") from None
            current = self.path.stat(follow_symlinks=False)
            if (current.st_dev, current.st_ino) != (metadata.st_dev, metadata.st_ino):
                raise RuntimeError("socket path changed during stale-socket verification") from None
            self.path.unlink()
        else:
            raise RuntimeError("another engine is already listening on the configured socket")
        finally:
            probe.close()

    def _peer_allowed(self, conn: socket.socket) -> bool:
        if not hasattr(socket, "SO_PEERCRED"):
            return True  # Filesystem mode 0600 remains the authorization boundary.
        try:
            credentials = conn.getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")
            )
            _pid, uid, _gid = struct.unpack("3i", credentials)
            return uid in self.allowed_uids
        except OSError:
            return False

    def _serve_connection(self, conn: socket.socket) -> None:
        try:
            if not self._peer_allowed(conn):
                self._send(conn, failure(None, -32001, "Unauthorized local client"))
                return
            frame = self._read_frame(conn)
            request = parse_request(frame)
            response = self.dispatcher.handle(request)
            self._send(conn, response)
        except RpcFault as exc:
            self._send(conn, failure(None, exc.code, exc.message, exc.data))
        except (OSError, TimeoutError):
            # A disconnected or stalled peer gets no diagnostic that could expose local data.
            return
        finally:
            conn.close()

    def _read_frame(self, conn: socket.socket) -> bytes:
        chunks = bytearray()
        while True:
            data = conn.recv(min(4096, self.max_message_bytes + 1 - len(chunks)))
            if not data:
                raise RpcFault(-32700, "Incomplete JSON-RPC frame")
            newline = data.find(b"\n")
            if newline >= 0:
                if newline != len(data) - 1:
                    raise RpcFault(-32600, "One request per connection is required")
                chunks.extend(data[:newline])
                if len(chunks) > self.max_message_bytes:
                    raise RpcFault(-32700, "Message too large")
                return bytes(chunks)
            chunks.extend(data)
            if len(chunks) > self.max_message_bytes:
                raise RpcFault(-32700, "Message too large")

    def _send(self, conn: socket.socket, payload: dict) -> None:
        try:
            try:
                frame = (
                    json.dumps(
                        payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")
                    ).encode("utf-8")
                    + b"\n"
                )
            except (TypeError, ValueError):
                frame = b'{"jsonrpc":"2.0","id":null,"error":{"code":-32603,"message":"Internal engine error"}}\n'
            if len(frame) > self.max_message_bytes:
                frame = (
                    json.dumps(
                        failure(None, -32603, "Response exceeds message limit"),
                        separators=(",", ":"),
                    ).encode("utf-8")
                    + b"\n"
                )
            conn.sendall(frame)
        except OSError:
            return

    def close(self) -> None:
        if self._stop.is_set() and self._listener is None:
            return
        self._stop.set()
        listener, self._listener = self._listener, None
        if listener is not None:
            try:
                listener.close()
            except OSError:
                pass
        self._executor.shutdown(wait=True, cancel_futures=True)
        if self._socket_identity is not None:
            try:
                metadata = self.path.stat(follow_symlinks=False)
                if (metadata.st_dev, metadata.st_ino) == self._socket_identity and stat.S_ISSOCK(
                    metadata.st_mode
                ):
                    self.path.unlink()
            except FileNotFoundError:
                pass
            self._socket_identity = None
