"""UI-only formatting helpers for VM details returned by the Engine."""

from __future__ import annotations

from plaivid_ui.engine_client.dto import VMDetail, VMRecord


def resolve_console_port(record: VMRecord, detail: VMDetail | None = None) -> int | None:
    if record.process is not None and record.process.port is not None:
        return record.process.port
    if record.object.configured_port is not None:
        return record.object.configured_port
    if detail is not None and detail.console is not None:
        return detail.console.port
    return None


def describe_host(
    node: str | None,
    local_hostname: str | None = None,
    local_node_id: str | None = None,
    *,
    local_node_name: str | None = None,
) -> str:
    raw = (node or "").strip()
    if not raw or raw == "—":
        return "—"
    if raw.casefold() == "auto":
        return raw
    hostname = (local_hostname or "").strip() or None
    identifiers = (local_node_id, local_node_name, hostname)
    if not any(value is not None and raw.casefold() == value.strip().casefold() for value in identifiers):
        return raw
    if hostname is None or raw.casefold() == hostname.casefold():
        return hostname or raw
    return f"{raw} ({hostname})"
