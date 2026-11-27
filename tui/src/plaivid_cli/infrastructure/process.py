"""Bounded subprocess execution for local PVM commands.

Arguments are passed as a vector and are never interpreted by a shell. Output is
continuously drained but only a configured prefix is retained in memory.
"""

from __future__ import annotations

import math
import os
import signal
import subprocess
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


class ProcessError(RuntimeError):
    """Safe process-boundary error; deliberately excludes argv and raw output."""


class ProcessStartError(ProcessError):
    """A configured local executable could not be started."""


class ProcessTimeout(ProcessError):
    """The command exceeded its deadline; ``reaped`` reports direct-child cleanup."""

    def __init__(self, *, reaped: bool) -> None:
        super().__init__("local command timed out")
        self.reaped = reaped


class ProcessCleanupError(ProcessError):
    """The direct child could not be reaped within the cleanup deadline."""


@dataclass(frozen=True, slots=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str
    stdout_truncated: bool
    stderr_truncated: bool
    elapsed_seconds: float


class _Capture:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.parts: list[bytes] = []
        self.size = 0
        self.truncated = False
        self.lock = threading.Lock()

    def append(self, data: bytes) -> None:
        with self.lock:
            keep = max(0, self.limit - self.size)
            if keep:
                fragment = data[:keep]
                self.parts.append(fragment)
                self.size += len(fragment)
            if len(data) > keep:
                self.truncated = True

    def text(self) -> str:
        with self.lock:
            raw = b"".join(self.parts)
        return raw.decode("utf-8", errors="replace")


def _safe_child_environment() -> dict[str, str]:
    """Keep command lookup and locale/user context; omit ambient credentials."""
    return {
        key: value
        for key, value in os.environ.items()
        if key in {"PATH", "HOME", "LANG"} or key.startswith("LC_")
    }


class ProcessRunner:
    """Run one argv command with bounded output and POSIX process-group cleanup."""

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        max_output_bytes: int = 1_048_576,
        terminate_grace: float = 2.0,
        cwd: str | Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        if max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be positive")
        if not math.isfinite(terminate_grace) or terminate_grace <= 0:
            raise ValueError("terminate_grace must be finite and positive")
        self.timeout = timeout
        self.max_output_bytes = max_output_bytes
        self.terminate_grace = terminate_grace
        self.cwd = str(cwd) if cwd is not None else None
        self.env = dict(env) if env is not None else _safe_child_environment()

    def run(self, argv: Sequence[str], *, timeout: float | None = None) -> ProcessResult:
        if isinstance(argv, (str, bytes)) or not argv:
            raise ValueError("argv must be a non-empty sequence of strings")
        command = tuple(argv)
        if any(not isinstance(part, str) or not part for part in command):
            raise ValueError("argv must contain non-empty strings")
        deadline = self.timeout if timeout is None else timeout
        if not math.isfinite(deadline) or deadline <= 0:
            raise ValueError("timeout must be finite and positive")

        started = time.monotonic()
        try:
            child = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                close_fds=True,
                cwd=self.cwd,
                env=self.env,
                start_new_session=(os.name == "posix"),
                bufsize=0,
            )
        except OSError as exc:
            raise ProcessStartError("could not start configured local command") from exc

        stdout = _Capture(self.max_output_bytes)
        stderr = _Capture(self.max_output_bytes)
        readers: list[threading.Thread] = []
        assert child.stdout is not None and child.stderr is not None

        def drain(pipe: object, capture: _Capture) -> None:
            try:
                while True:
                    chunk = pipe.read(8192)  # type: ignore[attr-defined]
                    if not chunk:
                        break
                    capture.append(chunk)
            except (OSError, ValueError):
                return

        for pipe, capture, name in (
            (child.stdout, stdout, "stdout"), (child.stderr, stderr, "stderr")
        ):
            reader = threading.Thread(
                target=drain, args=(pipe, capture), name=f"plaivid-{name}-drain", daemon=True
            )
            reader.start()
            readers.append(reader)

        try:
            child.wait(timeout=deadline)
        except subprocess.TimeoutExpired as exc:
            self._kill_process_tree(child)
            try:
                child.wait(timeout=self.terminate_grace)
            except subprocess.TimeoutExpired as cleanup_exc:
                self._close_pipes(child)
                raise ProcessCleanupError("timed-out local child could not be reaped") from cleanup_exc
            self._finish_readers(readers, child)
            raise ProcessTimeout(reaped=True) from exc

        self._finish_readers(readers, child)
        return ProcessResult(
            returncode=child.returncode,
            stdout=stdout.text(),
            stderr=stderr.text(),
            stdout_truncated=stdout.truncated,
            stderr_truncated=stderr.truncated,
            elapsed_seconds=max(0.0, time.monotonic() - started),
        )

    def _finish_readers(self, readers: list[threading.Thread], child: subprocess.Popen[bytes]) -> None:
        for reader in readers:
            reader.join(timeout=self.terminate_grace)
        if any(reader.is_alive() for reader in readers):
            self._kill_process_tree(child)
            self._close_pipes(child)
            for reader in readers:
                reader.join(timeout=0.05)
            if any(reader.is_alive() for reader in readers):
                raise ProcessCleanupError("process output readers did not stop after cleanup")

    @staticmethod
    def _kill_process_tree(child: subprocess.Popen[bytes]) -> None:
        """Kill the isolated POSIX process group; fall back to the direct child."""
        if os.name == "posix":
            try:
                os.killpg(child.pid, signal.SIGKILL)
                return
            except ProcessLookupError:
                return
            except OSError:
                pass
        try:
            child.kill()
        except ProcessLookupError:
            pass

    @staticmethod
    def _close_pipes(child: subprocess.Popen[bytes]) -> None:
        for pipe in (child.stdout, child.stderr):
            if pipe is not None:
                try:
                    pipe.close()
                except OSError:
                    pass
