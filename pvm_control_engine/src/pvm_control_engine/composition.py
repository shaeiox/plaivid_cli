"""Explicit construction of the Engine runtime dependency graph."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path

from pvm_control_engine.application.collection import CollectionCoordinator
from pvm_control_engine.application.service import EngineService
from pvm_control_engine.application.services import PlaividApplication
from pvm_control_engine.application.session_manager import SessionManager
from pvm_control_engine.auth.provider import AuthProvider
from pvm_control_engine.auth.session_store import SessionStore
from pvm_control_engine.config import Settings
from pvm_control_engine.infrastructure.audit import ReadOnlyAuditAdapter
from pvm_control_engine.infrastructure.process import ProcessRunner
from pvm_control_engine.infrastructure.pvm.adapter import LocalPvmAdapter
from pvm_control_engine.infrastructure.pvm.sbell import SbellClient
from pvm_control_engine.infrastructure.sbell.commands.registry import build_command_registry
from pvm_control_engine.infrastructure.sbell.commands.vm.common import VMOperationCoordinator
from pvm_control_engine.ipc.dispatcher import RpcDispatcher
from pvm_control_engine.ipc.server import UnixRpcServer


@dataclass(slots=True)
class EngineRuntime:
    """Own the serving lifecycle and all long-lived coordinators."""

    service: EngineService
    server: UnixRpcServer
    operations: VMOperationCoordinator
    collection: CollectionCoordinator
    _close_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    def serve(self) -> None:
        """Serve requests until the Unix RPC server is asked to stop."""
        self.server.serve_forever()

    def close(self) -> None:
        """Close owned resources once, even if an earlier close step raises."""
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
            try:
                self.server.close()
            finally:
                try:
                    self.operations.close()
                finally:
                    self.collection.close()


def build_runtime(
    settings: Settings,
    socket_path: str | Path,
    *,
    allowed_uids=None,
    max_workers: int = 4,
    socket_mode: int = 0o600,
) -> EngineRuntime:
    """Compose Engine adapters, application services, registry, and RPC transport."""
    runner = ProcessRunner(
        timeout=settings.process_timeout, max_output_bytes=settings.max_output_bytes
    )
    sbell = SbellClient(
        settings.sbell_argv,
        runner,
        allow_credential_argv=settings.allow_credential_argv,
    )
    provider = LocalPvmAdapter(
        sbell,
        runner,
        settings.running_vms_argv,
        allow_credential_argv=settings.allow_credential_argv,
        action_timeout=settings.action_timeout,
    )
    collection = CollectionCoordinator(provider, refresh_interval=settings.refresh_interval)
    operations: VMOperationCoordinator | None = None
    try:
        operations = VMOperationCoordinator(provider, collection, settings)
        audit = ReadOnlyAuditAdapter(settings.audit_database)
        application = PlaividApplication(provider, collection, settings, audit)
        store = SessionStore(settings.session_file)
        sessions = SessionManager(provider, settings, store)
        auth = AuthProvider(store, provider)
        registry = build_command_registry(
            provider,
            application,
            sessions,
            auth,
            audit,
            operations,
            sbell,
            action_timeout=settings.action_timeout,
        )
        service = EngineService(application=application, auth=auth, registry=registry)
        server = UnixRpcServer(
            socket_path,
            RpcDispatcher(service),
            allowed_uids=allowed_uids,
            max_workers=max_workers,
            socket_mode=socket_mode,
        )
    except BaseException:
        try:
            if operations is not None:
                operations.close()
        finally:
            collection.close()
        raise
    assert operations is not None
    return EngineRuntime(service, server, operations, collection)
