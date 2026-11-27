# Human-readable documentation for `server.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/ipc/server.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Bounded JSON-RPC server over a private Unix-domain stream socket.

## 2. Functional summary

Bounded JSON-RPC server over a private Unix-domain stream socket.

## 3. Inputs and outputs

This module exposes the declared classes and their constructors. Constructor arguments are shown in the method inventory; data fields and defaults are listed in the class section.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `UnixRpcServer.__init__(self, path: str | Path, dispatcher: RpcDispatcher, *, allowed_uids=None, max_workers: int=4, max_message_bytes: int=MAX_MESSAGE_BYTES, socket_mode: int=384) -> None`

Calls `Path(path).expanduser().absolute`, `frozenset`, `ThreadPoolExecutor`, `threading.BoundedSemaphore`, `threading.Event`. Reads or updates `self.socket_mode`, `self.path`, `self.dispatcher`, `self.allowed_uids`, `self.max_workers`, `self.max_message_bytes`. No explicit return statement; the function returns `None` unless an exception interrupts execution. Can raise `ValueError('max_workers must be positive')`, `ValueError('max_message_bytes must be between 1024 and the protocol maximum')`, `ValueError('socket_mode must be 0600 or 0660')`.

### `UnixRpcServer.serve_forever(self) -> None`

Calls `self._bind`, `self.close`, `self._stop.is_set`, `conn.settimeout`, `future.add_done_callback`. Reads or updates `listener`, `(conn, _)`, `future`. No explicit return statement; the function returns `None` unless an exception interrupts execution. Can raise `re-raise`.

### `UnixRpcServer.request_shutdown(self) -> None`

Ask the accept loop to stop; it will drain workers and unlink its socket.

### `UnixRpcServer._bind(self) -> None`

Calls `self.path.parent.mkdir`, `self._remove_stale_socket`, `socket.socket`, `listener.bind`, `self.path.stat`. Reads or updates `listener`, `bound`, `self._listener`, `metadata`, `self._socket_identity`. No explicit return statement; the function returns `None` unless an exception interrupts execution. Can raise `re-raise`.

### `UnixRpcServer._remove_stale_socket(self) -> None`

Calls `socket.socket`, `self.path.stat`, `RuntimeError`, `probe.settimeout`, `probe.connect`. Reads or updates `probe`, `metadata`, `current`. Explicit return value(s): `None`. Can raise `RuntimeError('socket path exists and is not an owned socket')`, `RuntimeError('another engine is already listening on the configured socket')`, `RuntimeError('could not verify an existing socket path')`, `RuntimeError('socket path changed during stale-socket verification')`.

### `UnixRpcServer._peer_allowed(self, conn: socket.socket) -> bool`

Calls `hasattr`, `conn.getsockopt`, `struct.unpack`, `struct.calcsize`. Reads or updates `credentials`, `(_pid, uid, _gid)`. Explicit return value(s): `True`, `uid in self.allowed_uids`, `False`.

### `UnixRpcServer._serve_connection(self, conn: socket.socket) -> None`

Calls `self._read_frame`, `parse_request`, `self.dispatcher.handle`, `self._send`, `conn.close`. Reads or updates `frame`, `request`, `response`. Explicit return value(s): `None`.

### `UnixRpcServer._read_frame(self, conn: socket.socket) -> bytes`

Calls `bytearray`, `conn.recv`, `data.find`, `chunks.extend`, `min`. Reads or updates `chunks`, `data`, `newline`. Explicit return value(s): `bytes(chunks)`. Can raise `RpcFault(-32700, 'Incomplete JSON-RPC frame')`, `RpcFault(-32700, 'Message too large')`, `RpcFault(-32600, 'One request per connection is required')`.

### `UnixRpcServer._send(self, conn: socket.socket, payload: dict) -> None`

Calls `conn.sendall`, `len`, `json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode`, `json.dumps(failure(None, -32603, 'Response exceeds message limit'), separators=(',', ':')).encode`, `json.dumps`. Reads or updates `frame`. Explicit return value(s): `None`.

### `UnixRpcServer.close(self) -> None`

Calls `self._stop.set`, `self._executor.shutdown`, `self._stop.is_set`, `listener.close`, `self.path.stat`. Reads or updates `(listener, self._listener)`, `self._socket_identity`, `metadata`. Explicit return value(s): `None`.

## 6. Classes and data structures

### `UnixRpcServer`

- **Bases:** no explicit base class.
- **Description:** Class declared with bases: no explicit base class.
- **Methods:** `__init__`, `serve_forever`, `request_shutdown`, `_bind`, `_remove_stale_socket`, `_peer_allowed`, `_serve_connection`, `_read_frame`, `_send`, `close`.

## 7. Decision-making logic

The following branch conditions are present in the implementation; each selects the corresponding source-code path:

- `max_workers < 1`
- `not 1024 <= max_message_bytes <= MAX_MESSAGE_BYTES`
- `socket_mode not in {384, 432}`
- `not stat.S_ISSOCK(metadata.st_mode) or metadata.st_uid != os.getuid()`
- `not hasattr(socket, 'SO_PEERCRED')`
- `self._stop.is_set() and self._listener is None`
- `listener is not None`
- `self._socket_identity is not None`
- `not self._peer_allowed(conn)`
- `not data`
- `newline >= 0`
- `len(chunks) > self.max_message_bytes`
- `len(frame) > self.max_message_bytes`
- `allowed_uids is None` (with an `else` branch)
- `not self._slots.acquire(blocking=False)`
- `bound and self._socket_identity is not None`
- `exc.errno != errno.ECONNREFUSED`
- `(current.st_dev, current.st_ino) != (metadata.st_dev, metadata.st_ino)`
- `newline != len(data) - 1`
- `len(chunks) > self.max_message_bytes`
- `(metadata.st_dev, metadata.st_ino) == self._socket_identity and stat.S_ISSOCK(metadata.st_mode)`
- `self._stop.is_set()`
- `(metadata.st_dev, metadata.st_ino) == self._socket_identity`

## 8. Loops and repeated operations

Iteration is performed by the following loops/comprehensions:

- `while True`
- `while not self._stop.is_set()`

## 9. Error handling

The module contains these exception-handling clauses:

- `try` block (line 54) handles: no typed handler.
- `try` block (line 89) handles: Exception.
- `try` block (line 111) handles: FileNotFoundError.
- `try` block (line 118) handles: OSError.
- `try` block (line 136) handles: OSError.
- `try` block (line 146) handles: RpcFault, (OSError, TimeoutError).
- `try` block (line 181) handles: OSError.
- `try` block (line 182) handles: (TypeError, ValueError).
- `try` block (line 209) handles: OSError.
- `try` block (line 215) handles: FileNotFoundError.
- `try` block (line 56) handles: TimeoutError, OSError.
- `try` block (line 69) handles: RuntimeError.
- `try` block (line 100) handles: FileNotFoundError.

Explicitly raised exception expressions: `ValueError('max_workers must be positive')`, `ValueError('max_message_bytes must be between 1024 and the protocol maximum')`, `ValueError('socket_mode must be 0600 or 0660')`, `RuntimeError('socket path exists and is not an owned socket')`, `RuntimeError('another engine is already listening on the configured socket')`, `re-raise`, `RpcFault(-32700, 'Incomplete JSON-RPC frame')`, `RpcFault(-32700, 'Message too large')`, `RuntimeError('could not verify an existing socket path')`, `RuntimeError('socket path changed during stale-socket verification')`, `RpcFault(-32600, 'One request per connection is required')`.

## 10. Dependencies and interactions

- **Project imports:** `.dispatcher`, `.protocol`.
- **Standard-library/third-party imports:** `__future__`, `errno`, `json`, `os`, `socket`, `stat`, `struct`, `threading`, `concurrent.futures`, `pathlib`.

## 11. Real-world scenario

Bounded JSON-RPC server over a private Unix-domain stream socket.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`server.py` is part of `pvm_control_engine`. Bounded JSON-RPC server over a private Unix-domain stream socket. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.
