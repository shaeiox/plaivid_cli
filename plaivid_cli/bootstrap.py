"""Single composition root and process entry point."""

from __future__ import annotations

import logging
import sys
from collections.abc import Sequence
from dataclasses import dataclass

from plaivid_cli.application.collection import CollectionCoordinator
from plaivid_cli.application.operations import OperationCoordinator
from plaivid_cli.application.services import PlaividApplication
from plaivid_cli.application.session import SessionManager, SessionStore
from plaivid_cli.cli import build_parser, configuration_command, run_command
from plaivid_cli.config import ConfigurationError, Settings, load_settings
from plaivid_cli.infrastructure.audit import ReadOnlyAuditAdapter
from plaivid_cli.infrastructure.diagnostics import configure_logging
from plaivid_cli.infrastructure.process import ProcessRunner
from plaivid_cli.infrastructure.pvm.adapter import LocalPvmAdapter
from plaivid_cli.infrastructure.pvm.sbell import SbellClient


@dataclass(slots=True)
class Runtime:
    settings: Settings
    application: PlaividApplication
    operations: OperationCoordinator
    sessions: SessionManager
    collection: CollectionCoordinator

    def close(self) -> None:
        self.operations.close()
        self.collection.close()


def build_runtime(settings: Settings) -> Runtime:
    """Construct the one provider, coordinator set, and application facade."""
    runner = ProcessRunner(
        timeout=settings.process_timeout,
        max_output_bytes=settings.max_output_bytes,
    )
    sbell = SbellClient(settings.sbell_argv, runner)
    provider = LocalPvmAdapter(
        sbell,
        runner,
        settings.running_vms_argv,
        allow_credential_argv=settings.allow_credential_argv,
    )
    collection = CollectionCoordinator(provider, refresh_interval=settings.refresh_interval)
    audit = ReadOnlyAuditAdapter(settings.audit_database)
    application = PlaividApplication(provider, collection, settings, audit)
    operations = OperationCoordinator(provider, collection, settings)
    sessions = SessionManager(provider, settings, SessionStore(settings.session_file))
    return Runtime(settings, application, operations, sessions, collection)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "help":
        parser.print_help()
        return 0
    try:
        settings = load_settings()
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    if args.command in {"config", "diagnostics"}:
        return configuration_command(settings, as_json=args.json)
    logger = configure_logging(verbose=False)
    logger.setLevel(getattr(logging, settings.log_level))
    if settings.allow_credential_argv:
        logger.warning(
            "PLAIVID_ALLOW_CREDENTIAL_ARGV is enabled; sbell credentials/tokens may be visible in process arguments"
        )
    runtime = build_runtime(settings)
    try:
        return run_command(
            args,
            application=runtime.application,
            operations=runtime.operations,
            sessions=runtime.sessions,
            settings=settings,
        )
    finally:
        runtime.close()
