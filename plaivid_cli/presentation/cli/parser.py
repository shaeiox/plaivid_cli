"""Argparse grammar for supported CLI commands."""

from __future__ import annotations

import argparse

from plaivid_cli.domain.models import Action
from plaivid_cli.version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="plaivid",
        description="Linux-local terminal client for Plaivid PVM management.",
        epilog=(
            "Credential argv exposure is unresolved and login is blocked by default. "
            "Bulk operations require PLAIVID_MAX_INVENTORY_AGE_SECONDS and complete fresh inventory."
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
        operation.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return parser
