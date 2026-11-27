"""Engine CLI, configuration boundary, and process lifecycle policy."""

from __future__ import annotations

import argparse
import getpass
import os
import signal
import sys
from collections.abc import Sequence
from pathlib import Path

from pvm_control_engine.application.session_manager import SessionManager
from pvm_control_engine.auth.session_store import SessionStore
from pvm_control_engine.composition import EngineRuntime, build_runtime
from pvm_control_engine.config import ConfigurationError, Settings, load_settings
from pvm_control_engine.infrastructure.process import ProcessRunner
from pvm_control_engine.infrastructure.pvm.adapter import LocalPvmAdapter
from pvm_control_engine.infrastructure.pvm.sbell import SbellClient
from pvm_control_engine.infrastructure.sbell.commands.user.login import UserLogin


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


def _socket_path(args: argparse.Namespace, settings: Settings) -> str:
    configured_path = args.socket or os.environ.get("PLAIVID_CONTROL_SOCKET")
    if configured_path:
        return configured_path
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", str(settings.state_dir))
    return str(Path(runtime_dir) / "pvm-control-engine.sock")


def _run_runtime(runtime: EngineRuntime) -> int:
    old_handler = None
    handler_installed = False
    try:
        old_handler = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGTERM, lambda _signum, _frame: runtime.server.request_shutdown())
        handler_installed = True
        try:
            runtime.serve()
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
        try:
            if handler_installed:
                signal.signal(signal.SIGTERM, old_handler)
        finally:
            runtime.close()


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        settings = load_settings()
        if args.command == "login":
            return _interactive_login(settings, args.username)
        allowed_uids = {os.getuid(), *(args.allow_uid or [])}
        runtime = build_runtime(
            settings,
            _socket_path(args, settings),
            allowed_uids=allowed_uids,
            max_workers=args.max_workers,
            socket_mode=args.socket_mode,
        )
    except (ConfigurationError, ValueError, OSError, RuntimeError) as exc:
        print(f"pvm-control-engine: {exc}", file=sys.stderr)
        return 2
    return _run_runtime(runtime)
