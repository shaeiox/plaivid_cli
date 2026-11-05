"""Top-level one-shot command dispatch and error-to-exit mapping."""

from __future__ import annotations

import argparse
import sys

from plaivid_cli.application.operations import OperationCoordinator
from plaivid_cli.application.services import PlaividApplication
from plaivid_cli.application.session import SessionManager
from plaivid_cli.config import Settings
from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import Action, ErrorKind

from .operations import EXIT_FAILURE, EXIT_OK, EXIT_REJECTED, _operate, _session
from .parser import build_parser
from .reads import _audit, _detail, _host, _inventory
from .serialization import configuration_command

EXIT_PARTIAL = 3


def run_command(
    args: argparse.Namespace,
    *,
    application: PlaividApplication,
    operations: OperationCoordinator,
    sessions: SessionManager,
    settings: Settings,
) -> int:
    if args.command in {None, "tui"}:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            print(
                "The Textual dashboard requires an interactive TTY; use a one-shot command.",
                file=sys.stderr,
            )
            return EXIT_REJECTED
        from plaivid_cli.presentation.tui import PlaividTui

        PlaividTui(application, operations, sessions).run()
        return EXIT_OK
    if args.command == "help":
        build_parser().print_help()
        return EXIT_OK
    if args.command in {"config", "diagnostics"}:
        return configuration_command(settings, as_json=args.json)

    try:
        if args.command == "audit":
            return _audit(application, args.limit, as_json=args.json)
        if args.command == "logout":
            try:
                session = _session(sessions, settings)
            except AppError as exc:
                if exc.code != "LOGIN_REQUIRED":
                    raise
                sessions.clear_local_cache()
                print("Local session cache cleared; no valid PVM session was available.")
                return EXIT_OK
            sessions.logout(session)
            print("Local session cleared.")
            return EXIT_OK
        session = _session(sessions, settings)
        if args.command == "inventory":
            return _inventory(application, session, as_json=args.json)
        if args.command in {"host", "status", "overview"}:
            return _host(application, session, as_json=args.json)
        if args.command == "detail":
            return _detail(application, session, args.uuid, as_json=args.json)
        if args.command in {action.value for action in Action}:
            return _operate(application, operations, session, args)
        print(f"Unsupported command: {args.command}", file=sys.stderr)
        return EXIT_REJECTED
    except AppError as exc:
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return (
            EXIT_REJECTED
            if exc.kind in {ErrorKind.POLICY, ErrorKind.AUTHENTICATION}
            else EXIT_FAILURE
        )
    except (OSError, ValueError) as exc:
        print(f"Input/configuration error: {exc}", file=sys.stderr)
        return EXIT_REJECTED
