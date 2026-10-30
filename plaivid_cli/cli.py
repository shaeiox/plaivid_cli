"""Argparse one-shot commands over the application use cases."""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from dataclasses import asdict

from plaivid_cli.application.operations import OperationCoordinator
from plaivid_cli.application.services import PlaividApplication, as_inventory
from plaivid_cli.application.session import SessionManager
from plaivid_cli.config import Settings
from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import (
    Action,
    CollectionStatus,
    ErrorKind,
    HostMetrics,
    HostStatus,
    InventoryData,
    OperationState,
    PvmSession,
    VMDetail,
)
from plaivid_cli.domain.policies import action_policy
from plaivid_cli.domain.redaction import redact_text
from plaivid_cli.version import __version__

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_REJECTED = 2
EXIT_PARTIAL = 3
EXIT_UNKNOWN = 4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="plaivid",
        description="Linux-local terminal client for Plaivid PVM management.",
        epilog=(
            "Credential argv exposure is unresolved and login is blocked by default. "
            "Bulk operations require PLAIVID_MAX_INVENTORY_AGE_SECONDS and exact approval."
        ),
    )
    parser.add_argument("--version", action="version", version=f"plaivid {__version__}")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("tui", help="open the interactive Textual dashboard")
    inventory = commands.add_parser("inventory", help="list VM object state and process evidence")
    inventory.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    host = commands.add_parser(
        "host", aliases=("status", "overview"), help="show host and monitoring status"
    )
    host.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    detail = commands.add_parser("detail", help="show one VM's detailed configuration")
    detail.add_argument("uuid", help="canonical VM UUID")
    detail.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    audit = commands.add_parser("audit", help="read recent local audit rows")
    audit.add_argument("--limit", type=int, default=20, choices=range(1, 501))
    audit.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    commands.add_parser("logout", help="log out and clear the local token cache")
    config = commands.add_parser(
        "config", aliases=("diagnostics",), help="show validated, redacted runtime configuration"
    )
    config.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    commands.add_parser("help", help="show this help without contacting PVM")
    for action in Action:
        operation = commands.add_parser(action.value, help=f"submit a VM {action.value} command")
        operation.add_argument(
            "targets",
            nargs="+",
            help="UUID, exact name, unique name prefix, index, all, state:<state>, or process:<present|missing>",
        )
        operation.add_argument(
            "--approve",
            help="exact acknowledgement: ACTION UUID[,UUID...]; required for risky/bulk actions",
        )
        operation.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return parser


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
            print("The Textual dashboard requires an interactive TTY; use a one-shot command.", file=sys.stderr)
            return EXIT_REJECTED
        from plaivid_cli.tui import PlaividTui

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
        return EXIT_REJECTED if exc.kind in {ErrorKind.POLICY, ErrorKind.AUTHENTICATION} else EXIT_FAILURE
    except (OSError, ValueError) as exc:
        print(f"Input/configuration error: {exc}", file=sys.stderr)
        return EXIT_REJECTED


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
    username = input(f"Username [{settings.default_username}]: ").strip() or settings.default_username
    password = getpass.getpass("Password: ")
    session, _ = sessions.resume_or_login(username=username, password=password)
    return session


def _inventory(application: PlaividApplication, session: PvmSession, *, as_json: bool = False) -> int:
    _, section = application.inventory(session.token)
    value = section.value or section.last_good_value
    inventory = value if isinstance(value, InventoryData) else None
    if as_json:
        _print_json(_section_payload(section, inventory))
        return EXIT_OK if section.status is CollectionStatus.CURRENT else EXIT_PARTIAL
    if inventory is None:
        print(f"VM inventory unavailable · {section.status.value}: {redact_text(section.error or 'no data')}")
        return EXIT_PARTIAL
    print(f"VM inventory · {section.status.value} · generation {section.generation}")
    print(" #  VM name                 UUID                                  OBJECT STATE  PROCESS")
    records = sorted(
        inventory.records,
        key=lambda record: (0 if record.process_seen else 1, record.name.casefold(), record.uuid),
    )
    for index, record in enumerate(records, start=1):
        process = f"observed pid={record.process.pid}" if record.process else "not observed"
        issue = " [state conflict]" if record.state_disagreed else ""
        name = redact_text(record.name)[:22]
        state = redact_text(record.state)
        print(f"{index:2}  {name:22}  {record.uuid}  {state:12}  {process}{issue}")
    for issue in inventory.quality_issues:
        print(f"Quality: {redact_text(issue)}")
    if section.error:
        print(f"Collection note: {redact_text(section.error)}")
    return EXIT_PARTIAL if section.status is not CollectionStatus.CURRENT else EXIT_OK


def _host(application: PlaividApplication, session: PvmSession, *, as_json: bool = False) -> int:
    snapshot = application.refresh(session.token, sections=("host_status", "host_metrics"))
    status_section = snapshot.section("host_status")
    metrics_section = snapshot.section("host_metrics")
    status_value = (status_section.value or status_section.last_good_value) if status_section else None
    metrics_value = (metrics_section.value or metrics_section.last_good_value) if metrics_section else None
    status = status_value if isinstance(status_value, HostStatus) else None
    metrics = metrics_value if isinstance(metrics_value, HostMetrics) else None
    if as_json:
        _print_json(
            {
                "command": "host",
                "sections": {
                    "host_status": _section_payload(status_section, status),
                    "host_metrics": _section_payload(metrics_section, metrics),
                },
            }
        )
        return EXIT_OK if all(
            item is not None and item.status is CollectionStatus.CURRENT
            for item in (status_section, metrics_section)
        ) else EXIT_PARTIAL
    if status is None and metrics is None:
        print("Host status unavailable.")
        return EXIT_PARTIAL
    if status is not None:
        print(redact_text(
            f"Host {status.name or '—'} ({status.ip or '—'}) · sball_state={status.sball_state or '—'} "
            f"· node_state={status.node_state or '—'} · version={status.version or '—'}"
        ))
        print(redact_text(
            f"CPU {status.cpu_pct if status.cpu_pct is not None else '—'}% "
            f"({status.cpu_count if status.cpu_count is not None else '—'} cores) · "
            f"RAM {_format_bytes(status.ram_used_bytes)} / {_format_bytes(status.ram_total_bytes)} · "
            f"storage free {_format_bytes(status.storage_available_bytes)} / "
            f"{_format_bytes(status.storage_total_bytes)}"
        ))
    if metrics is not None:
        print(redact_text(
            f"Metrics {metrics.hostname or '—'} · CPU {metrics.cpu_pct if metrics.cpu_pct is not None else '—'}% · "
            f"memory {_format_bytes(metrics.memory_used_bytes)} / {_format_bytes(metrics.memory_total_bytes)} · "
            f"interfaces {len(metrics.interfaces)} · mounts {len(metrics.storage)}"
        ))
    return EXIT_OK if all(
        item is None or item.status is CollectionStatus.CURRENT
        for item in (status_section, metrics_section)
    ) else EXIT_PARTIAL


def _detail(
    application: PlaividApplication,
    session: PvmSession,
    uuid: str,
    *,
    as_json: bool = False,
) -> int:
    section = application.detail(session.token, uuid)
    detail_value = section.value or section.last_good_value
    detail = detail_value if isinstance(detail_value, VMDetail) else None
    if as_json:
        _print_json(_section_payload(section, detail))
        return EXIT_OK if section.status is CollectionStatus.CURRENT else EXIT_PARTIAL
    if detail is None:
        print(f"VM detail unavailable · {section.status.value}: {section.error or 'no data'}")
        return EXIT_PARTIAL
    print(redact_text(f"{detail.name} · {detail.uuid} · state={detail.state}"))
    print(redact_text(
        f"Host {detail.host or '—'} · vCPU {detail.vcpu if detail.vcpu is not None else '—'} · "
        f"memory {detail.memory_mb if detail.memory_mb is not None else '—'} MB · "
        f"machine {detail.machine or '—'}"
    ))
    print(redact_text(f"Description: {detail.description or '—'}"))
    print(redact_text(
        f"CPU: {detail.cpu_model or '—'} · topology {detail.vcpu_topology or '—'} · UEFI {detail.uefi or '—'}"
    ))
    print(redact_text(
        f"Disks: {len(detail.disks)} · NICs: {len(detail.nics)} · console: {detail.console.kind if detail.console else '—'}"
    ))
    return EXIT_OK if section.status is CollectionStatus.CURRENT else EXIT_PARTIAL


def _audit(application: PlaividApplication, limit: int, *, as_json: bool = False) -> int:
    entries = application.recent_audit(limit)
    if as_json:
        _print_json({"command": "audit", "status": "current", "data": entries})
        return EXIT_OK
    print("READ-ONLY local audit · newest first")
    if not entries:
        print("No matching audit rows.")
        return EXIT_OK
    for entry in entries:
        status = "OK" if entry.succeeded else "FAILED"
        print(f"{entry.time}  {entry.user}  {entry.user_ip}  {entry.command}  {status}: {entry.result}")
    return EXIT_OK


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
    plan = operations.create_plan(
        action, selection.records, section, is_bulk=selection.is_bulk
    )
    policy = action_policy(action)
    confirmation_required = policy.confirm_single or (selection.is_bulk and policy.confirm_bulk)
    approval = None
    expected = plan.confirmation
    if args.approve is not None:
        approval = operations.approve(action, selection.records, section, confirmation=args.approve)
    elif confirmation_required:
        print(
            f"Approval required. Repeat with --approve {expected!r}. "
            "The approval is checked against this fresh inventory and exact UUID set.",
            file=sys.stderr,
        )
        return EXIT_REJECTED

    result = operations.execute(
        session.token,
        action,
        selection.records,
        section,
        is_bulk=selection.is_bulk,
        approval=approval,
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


def configuration_command(settings: Settings, *, as_json: bool = False) -> int:
    values = {
        "sbell_executable": settings.sbell_argv[0],
        "running_vms_executable": settings.running_vms_argv[0],
        "process_timeout_seconds": settings.process_timeout,
        "max_output_bytes_per_stream": settings.max_output_bytes,
        "refresh_interval_seconds": settings.refresh_interval,
        "state_directory": str(settings.state_dir),
        "session_file": str(settings.session_file),
        "default_username": settings.default_username,
        "credential_argv_acknowledged": settings.allow_credential_argv,
        "max_inventory_age_seconds": settings.max_inventory_age_seconds,
        "audit_database": str(settings.audit_database),
        "log_level": settings.log_level,
    }
    if as_json:
        _print_json({"command": "config", "status": "validated", "data": values})
    else:
        print("Validated runtime configuration (secrets and additional argv omitted):")
        for key, value in values.items():
            print(f"{key}: {value}")
    return EXIT_OK


def _section_payload(section, data):
    return {
        "status": section.status.value if section is not None else "unavailable",
        "generation": section.generation if section is not None else None,
        "source": section.source if section is not None else None,
        "attempted_at": section.attempted_at if section is not None else None,
        "succeeded_at": section.succeeded_at if section is not None else None,
        "error": section.error if section is not None else "section unavailable",
        "quality_issues": section.quality_issues if section is not None else (),
        "data": _json_data(data),
    }


def _json_data(value):
    if isinstance(value, InventoryData):
        return {
            "objects": value.objects,
            "process_rows": value.process_rows,
            "records": [
                {
                    "uuid": record.uuid,
                    "name": record.name,
                    "state": record.state,
                    "object": record.object,
                    "process": record.process,
                    "process_seen": record.process_seen,
                    "state_disagreed": record.state_disagreed,
                    "quality_issues": record.quality_issues,
                }
                for record in value.records
            ],
            "unmatched_process_rows": value.unmatched_process_rows,
            "quality_issues": value.quality_issues,
        }
    return value


def _redact_json(value):
    if isinstance(value, str):
        return redact_text(value)
    if hasattr(value, "__dataclass_fields__"):
        return _redact_json(asdict(value))
    if isinstance(value, dict):
        secret_keys = {"password", "token", "secret", "authorization", "session_token"}
        return {
            key: "[REDACTED]" if str(key).casefold() in secret_keys else _redact_json(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact_json(item) for item in value]
    return value


def _print_json(value) -> None:
    def encode(item):
        if hasattr(item, "isoformat"):
            return item.isoformat()
        raise TypeError(f"cannot serialize {type(item).__name__}")

    print(json.dumps(_redact_json(value), ensure_ascii=False, indent=2, default=encode))


def _format_bytes(value: int | None) -> str:
    if value is None:
        return "—"
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TiB"
