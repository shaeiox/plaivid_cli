"""Validated runtime configuration loaded at the composition boundary."""

from __future__ import annotations

import math
import os
import shlex
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


class ConfigurationError(ValueError):
    """A required runtime setting is invalid or unsafe."""


def _argv(env: Mapping[str, str], name: str, default: str) -> tuple[str, ...]:
    raw = env.get(name, default)
    try:
        parts = tuple(shlex.split(raw))
    except ValueError as exc:
        raise ConfigurationError(f"{name} contains invalid quoting") from exc
    if not parts or any(not part for part in parts):
        raise ConfigurationError(f"{name} must define a non-empty executable argv")
    return parts


def _positive_float(env: Mapping[str, str], name: str, default: str) -> float:
    raw = env.get(name, default)
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{name} must be numeric") from exc
    if not math.isfinite(value) or value <= 0:
        raise ConfigurationError(f"{name} must be a finite positive number")
    return value


def _optional_positive_float(env: Mapping[str, str], name: str) -> float | None:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be numeric") from exc
    if not math.isfinite(value) or value <= 0:
        raise ConfigurationError(f"{name} must be a finite positive number when configured")
    return value


def _enabled(env: Mapping[str, str], name: str) -> bool:
    return env.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    sbell_argv: tuple[str, ...]
    running_vms_argv: tuple[str, ...]
    process_timeout: float
    max_output_bytes: int
    refresh_interval: float
    state_dir: Path
    session_file: Path
    default_username: str
    allow_credential_argv: bool
    max_inventory_age_seconds: float | None
    audit_database: Path
    log_level: str


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if environ is None else environ
    state_home = Path(env.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
    state_dir = Path(env.get("PLAIVID_STATE_DIR", str(state_home / "plaivid"))).expanduser()
    output_raw = env.get("PLAIVID_MAX_OUTPUT_BYTES", "1048576")
    try:
        max_output = int(output_raw)
    except ValueError as exc:
        raise ConfigurationError("PLAIVID_MAX_OUTPUT_BYTES must be an integer") from exc
    if max_output < 1024:
        raise ConfigurationError("PLAIVID_MAX_OUTPUT_BYTES must be at least 1024")
    username = env.get("PLAIVID_USER", "manage").strip()
    if not username:
        raise ConfigurationError("PLAIVID_USER cannot be empty")
    log_level = env.get("PLAIVID_LOG_LEVEL", "WARNING").upper()
    if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ConfigurationError("PLAIVID_LOG_LEVEL is not a supported logging level")
    return Settings(
        sbell_argv=_argv(env, "PLAIVID_SBELL", "sudo sbell"),
        running_vms_argv=_argv(env, "PLAIVID_RUNNING_VMS", "pvm-running-vms"),
        process_timeout=_positive_float(env, "PLAIVID_CMD_TIMEOUT", "30"),
        max_output_bytes=max_output,
        refresh_interval=_positive_float(env, "PLAIVID_REFRESH", "3"),
        state_dir=state_dir,
        session_file=state_dir / "session.json",
        default_username=username,
        allow_credential_argv=_enabled(env, "PLAIVID_ALLOW_CREDENTIAL_ARGV"),
        max_inventory_age_seconds=_optional_positive_float(
            env, "PLAIVID_MAX_INVENTORY_AGE_SECONDS"
        ),
        audit_database=Path(env.get("PLAIVID_LOG_DB", "/var/log/pvm/messages.db")),
        log_level=log_level,
    )
