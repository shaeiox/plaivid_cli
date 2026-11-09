"""Consistent JSON conversion, redaction, and human formatting."""

from __future__ import annotations

import json
from dataclasses import asdict

from plaivid_cli.config import Settings
from plaivid_cli.domain.models import InventoryData
from plaivid_cli.domain.redaction import redact_text

EXIT_OK = 0


def configuration_command(settings: Settings, *, as_json: bool = False) -> int:
    values = {
        "sbell_executable": settings.sbell_argv[0],
        "running_vms_executable": settings.running_vms_argv[0],
        "process_timeout_seconds": settings.process_timeout,
        "action_timeout_seconds": settings.action_timeout,
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
