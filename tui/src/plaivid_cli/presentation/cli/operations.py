"""Session admission and lifecycle-command handling for one-shot CLI use."""

from __future__ import annotations

import argparse
import getpass
import sys

from plaivid_cli.application.operations import OperationCoordinator
from plaivid_cli.application.services import PlaividApplication, as_inventory
from plaivid_cli.application.session import SessionManager
from plaivid_cli.config import Settings
from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import Action, ErrorKind, OperationState, PvmSession

from .serialization import _print_json

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_REJECTED = 2
EXIT_PARTIAL = 3
EXIT_UNKNOWN = 4


def _session(sessions: SessionManager, settings: Settings) -> PvmSession:
    try:
        session, _ = sessions.resume_or_login()
        return session
    except AppError as exc:
        if exc.code != "LOGIN_REQUIRED":
            raise
    if not sys.stdin.isatty():
        raise AppError(
            ErrorKind.AUTHENTICATION,
            "no valid cached session is available in non-interactive mode",
            code="LOGIN_REQUIRED",
        )
    if not settings.allow_credential_argv:
        raise AppError(
            ErrorKind.POLICY,
            "login is blocked: sbell passes credentials in process arguments. "
            "Explicitly acknowledge with PLAIVID_ALLOW_CREDENTIAL_ARGV=1 only after review.",
            code="CREDENTIAL_ARGV_ACK_REQUIRED",
        )
    username = (
        input(f"Username [{settings.default_username}]: ").strip() or settings.default_username
    )
    password = getpass.getpass("Password: ")
    session, _ = sessions.resume_or_login(username=username, password=password)
    return session


def _operate(
    application: PlaividApplication,
    operations: OperationCoordinator,
    session: PvmSession,
    args: argparse.Namespace,
) -> int:
    action = Action(args.command)
    _, section = application.inventory(session.token)
    inventory = as_inventory(section)
    selectors = tuple(
        part.strip() for item in args.targets for part in item.split(",") if part.strip()
    )
    selection = application.resolve_targets(inventory, selectors)
    plan = operations.create_plan(action, selection.records, section, is_bulk=selection.is_bulk)
    result = operations.execute(
        session.token,
        action,
        selection.records,
        section,
        is_bulk=selection.is_bulk,
        plan=plan,
    )
    if args.json:
        _print_json({"command": action.value, "operation": result})
    else:
        for target in result.targets:
            print(f"{target.uuid}  {target.state.value}  {target.message}")
        print(f"Operation {result.operation_id}: {result.state.value} · {result.message}")
    exit_codes = {
        OperationState.SUCCEEDED: EXIT_OK,
        OperationState.FAILED: EXIT_FAILURE,
        OperationState.REJECTED: EXIT_REJECTED,
        OperationState.PARTIAL: EXIT_PARTIAL,
        OperationState.OUTCOME_UNKNOWN: EXIT_UNKNOWN,
        OperationState.COMMAND_ACCEPTED_UNCONFIRMED: EXIT_UNKNOWN,
        OperationState.CANCELLED_BEFORE_DISPATCH: EXIT_REJECTED,
    }
    return exit_codes.get(result.state, EXIT_FAILURE)
