"""Safe one-shot TUI-package CLI client for the Engine socket."""

from __future__ import annotations

import argparse
import json
import sys

from .client import EngineClient, EngineRpcError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plaivid", description="Plaivid terminal client")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("health", "inventory", "host", "overview", "audit", "logout", "tui"):
        commands.add_parser(name)
    detail = commands.add_parser("detail")
    detail.add_argument("uuid")
    commands.add_parser("login")
    operate = commands.add_parser("operate")
    operate.add_argument("action", choices=("start", "stop", "kill", "reset", "pause", "resume"))
    operate.add_argument("uuids", nargs="+")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    client = EngineClient()
    if args.command == "login":
        print(
            "Login is not available over IPC: the contract does not transmit passwords. "
            "Configure a trusted Engine-side authentication workflow.",
            file=sys.stderr,
        )
        return 2
    elif args.command == "logout":
        method, params = "session.logout", {}
    elif args.command == "health":
        method, params = "engine.health", {}
    elif args.command == "inventory":
        method, params = "vm.list", {}
    elif args.command == "host":
        method, params = "host.status", {}
    elif args.command == "overview":
        method, params = "overview.dashboard", {}
    elif args.command == "detail":
        method, params = "vm.get", {"uuid": args.uuid}
    elif args.command == "audit":
        method, params = "audit.recent", {}
    elif args.command == "operate":
        method = "vm.operate"
        params = {"action": args.action, "uuids": args.uuids} if len(args.uuids) > 1 else {"action": args.action, "uuid": args.uuids[0]}
    else:
        print("The Engine-client Textual UI is not yet connected; use the Engine socket CLI commands.", file=sys.stderr)
        return 2
    try:
        result = client.call(method, params)
    except EngineRpcError as exc:
        print(f"Engine error {exc.code}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
