"""Engine-only composition root and executable entry point."""

from __future__ import annotations

import argparse
import getpass
import os
import signal
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from pvm_control_engine.application.collection import CollectionCoordinator
from pvm_control_engine.application.service import EngineService
from pvm_control_engine.application.services import PlaividApplication
from pvm_control_engine.application.session_manager import SessionManager
from pvm_control_engine.auth.provider import AuthProvider
from pvm_control_engine.auth.session_store import SessionStore
from pvm_control_engine.config import ConfigurationError, Settings, load_settings
from pvm_control_engine.domain.models import Action
from pvm_control_engine.infrastructure.audit import ReadOnlyAuditAdapter
from pvm_control_engine.infrastructure.local.audit import LocalAudit
from pvm_control_engine.infrastructure.local.host_metrics import LocalHostMetrics
from pvm_control_engine.infrastructure.local.nic_samples import LocalNicSamples
from pvm_control_engine.infrastructure.process import ProcessRunner
from pvm_control_engine.infrastructure.pvm.adapter import LocalPvmAdapter
from pvm_control_engine.infrastructure.pvm.sbell import SbellClient
from pvm_control_engine.infrastructure.sbell.commands.desktop.operate import DesktopOperate
from pvm_control_engine.infrastructure.sbell.commands.monitoring.metrics import MonitoringMetrics
from pvm_control_engine.infrastructure.sbell.commands.network.nic_list import NetworkNicList
from pvm_control_engine.infrastructure.sbell.commands.registry import CommandRegistry
from pvm_control_engine.infrastructure.sbell.commands.sball.show import SballShow
from pvm_control_engine.infrastructure.sbell.commands.user.login import UserLogin
from pvm_control_engine.infrastructure.sbell.commands.user.logout import UserLogout
from pvm_control_engine.infrastructure.sbell.commands.user.objects import UserObjects
from pvm_control_engine.infrastructure.sbell.commands.user.whoami import UserWhoami
from pvm_control_engine.infrastructure.sbell.commands.vm.common import VMOperationCoordinator
from pvm_control_engine.infrastructure.sbell.commands.vm.kill import KillVM
from pvm_control_engine.infrastructure.sbell.commands.vm.pause import PauseVM
from pvm_control_engine.infrastructure.sbell.commands.vm.reset import ResetVM
from pvm_control_engine.infrastructure.sbell.commands.vm.resume import ResumeVM
from pvm_control_engine.infrastructure.sbell.commands.vm.start import StartVM
from pvm_control_engine.infrastructure.sbell.commands.vm.stop import StopVM
from pvm_control_engine.ipc.dispatcher import RpcDispatcher
from pvm_control_engine.ipc.server import UnixRpcServer
from pvm_control_engine.targets.vm_resolver import VMResolver


@dataclass(slots=True)
class EngineRuntime:
    service: EngineService
    server: UnixRpcServer
    operations: VMOperationCoordinator
    collection: CollectionCoordinator

    def close(self) -> None:
        self.server.close()
        self.operations.close()
        self.collection.close()


def build_runtime(
    settings: Settings,
    socket_path: str | Path,
    *,
    allowed_uids=None,
    max_workers: int = 4,
    socket_mode: int = 0o600,
) -> EngineRuntime:
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
    audit = ReadOnlyAuditAdapter(settings.audit_database)
    application = PlaividApplication(provider, collection, settings, audit)
    operations = VMOperationCoordinator(provider, collection, settings)
    store = SessionStore(settings.session_file)
    sessions = SessionManager(provider, settings, store)
    auth = AuthProvider(store, provider)
    resolver = VMResolver(application)
    vm_actions = {
        Action.START: StartVM(
            auth, resolver, operations, sbell, action_timeout=settings.action_timeout
        ),
        Action.STOP: StopVM(
            auth, resolver, operations, sbell, action_timeout=settings.action_timeout
        ),
        Action.KILL: KillVM(
            auth, resolver, operations, sbell, action_timeout=settings.action_timeout
        ),
        Action.RESET: ResetVM(
            auth, resolver, operations, sbell, action_timeout=settings.action_timeout
        ),
        Action.PAUSE: PauseVM(
            auth, resolver, operations, sbell, action_timeout=settings.action_timeout
        ),
        Action.RESUME: ResumeVM(
            auth, resolver, operations, sbell, action_timeout=settings.action_timeout
        ),
    }
    commands = {
        "user.login": UserLogin(sessions),
        "user.whoami": UserWhoami(provider),
        "user.logout": UserLogout(sessions, auth),
        "user.objects": UserObjects(application, auth),
        "sball.show": SballShow(application, auth),
        "monitoring.metrics": MonitoringMetrics(application, auth),
        "network.nic_list": NetworkNicList(application, auth),
        "local.host_metrics": LocalHostMetrics(application, auth),
        "local.nic_samples": LocalNicSamples(application, auth),
        "local.audit": LocalAudit(audit),
        "desktop.operate": DesktopOperate(auth, application, operations, vm_actions),
    }
    registry = CommandRegistry(commands, vm_actions)
    service = EngineService(
        application=application,
        auth=auth,
        registry=registry,
    )
    server = UnixRpcServer(
        socket_path,
        RpcDispatcher(service),
        allowed_uids=allowed_uids,
        max_workers=max_workers,
        socket_mode=socket_mode,
    )
    return EngineRuntime(service, server, operations, collection)


def _parse_socket_mode(value: str) -> int:
    try:
        mode = int(value, 8)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("socket mode must be 0600 or 0660") from exc
    if mode not in {0o600, 0o660}:
        raise argparse.ArgumentTypeError("socket mode must be 0600 or 0660")
    return mode


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pvm-control-engine")
    subparsers = parser.add_subparsers(dest="command", required=True)
    login = subparsers.add_parser("login", help="authenticate locally and store the Engine session")
    login.add_argument("--username", default=None, help="PVM username (defaults to PLAIVID_USER)")
    serve = subparsers.add_parser("serve", help="serve JSON-RPC on a Unix-domain socket")
    serve.add_argument(
        "--socket",
        default=None,
        help="socket path (default: PLAIVID_CONTROL_SOCKET or state directory)",
    )
    serve.add_argument(
        "--allow-uid",
        type=int,
        action="append",
        default=None,
        help="additional Linux UID authorized to use the socket (repeatable)",
    )
    serve.add_argument(
        "--socket-mode",
        type=_parse_socket_mode,
        default=0o600,
        metavar="0600|0660",
        help="socket permission mode: 0600 (default) or 0660",
    )
    serve.add_argument(
        "--max-workers",
        type=int,
        default=4,
        choices=range(1, 17),
        help="maximum simultaneous RPC requests (default: 4)",
    )
    return parser


def _interactive_login(settings: Settings, username: str | None) -> int:
    if not sys.stdin.isatty():
        print("pvm-control-engine login requires an interactive terminal", file=sys.stderr)
        return 2
    selected_user = (username or settings.default_username).strip()
    password = getpass.getpass(f"Password for {selected_user}: ")
    try:
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
        sessions = SessionManager(provider, settings, SessionStore(settings.session_file))
        session, _created = UserLogin(sessions).execute(selected_user, password)
    except Exception as exc:
        # Exception text may contain request detail: never echo it from auth setup.
        print(f"pvm-control-engine: authentication failed ({type(exc).__name__})", file=sys.stderr)
        return 1
    finally:
        password = ""
    print(f"Engine session stored for {session.username}.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        settings = load_settings()
        if args.command == "login":
            return _interactive_login(settings, args.username)
        socket_path = args.socket or os.environ.get("PLAIVID_CONTROL_SOCKET")
        if not socket_path:
            socket_path = str(
                Path(os.environ.get("XDG_RUNTIME_DIR", settings.state_dir))
                / "pvm-control-engine.sock"
            )
        allowed_uids = {os.getuid(), *(args.allow_uid or [])}
        runtime = build_runtime(
            settings,
            socket_path,
            allowed_uids=allowed_uids,
            max_workers=args.max_workers,
            socket_mode=args.socket_mode,
        )
    except (ConfigurationError, ValueError, OSError, RuntimeError) as exc:
        print(f"pvm-control-engine: {exc}", file=sys.stderr)
        return 2

    old_handler = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, lambda _signum, _frame: runtime.server.request_shutdown())
    try:
        runtime.server.serve_forever()
        return 0
    except KeyboardInterrupt:
        return 130
    except OSError as exc:
        print(
            f"pvm-control-engine: could not serve configured socket ({type(exc).__name__})",
            file=sys.stderr,
        )
        return 1
    finally:
        signal.signal(signal.SIGTERM, old_handler)
        runtime.close()
