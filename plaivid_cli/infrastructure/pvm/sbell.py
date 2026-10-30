"""Minimal argv-based adapter for the existing local ``sbell`` command."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import dataclass, field

from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import ErrorKind, PvmReply
from plaivid_cli.infrastructure.process import ProcessRunner

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True, slots=True)
class SbellResponse:
    status: str
    action_id: str | None
    errno: str | None
    what: str | None
    description: ET.Element | None = field(repr=False)
    returncode: int

    @property
    def ok(self) -> bool:
        return self.status == "success"

    @property
    def token(self) -> str | None:
        if self.description is None or not self.description.text:
            return None
        value = self.description.text.strip()
        return value or None

    def reply(self) -> PvmReply:
        return PvmReply(
            status=self.status,
            action_id=self.action_id,
            errno=self.errno,
            message=self.what,
            returncode=self.returncode,
        )


class SbellClient:
    """Run an existing ``sbell MODULE COMMAND PARAMS [TOKEN]`` invocation."""

    def __init__(self, executable: Sequence[str], runner: ProcessRunner) -> None:
        if not executable or any(not part for part in executable):
            raise ValueError("sbell executable must be a non-empty argv")
        self._executable = tuple(executable)
        self._runner = runner

    def call(
        self,
        module: str,
        command: str,
        params: str = "<params/>",
        token: str | None = None,
    ) -> SbellResponse:
        if not _IDENTIFIER.fullmatch(module) or not _IDENTIFIER.fullmatch(command):
            raise ValueError("invalid sbell module or command")
        if not isinstance(params, str) or not params:
            raise ValueError("sbell params must be non-empty XML text")
        argv = [*self._executable, module, command, params]
        if token:
            argv.append(token)
        result = self._runner.run(argv)
        if result.stdout_truncated:
            raise AppError(
                ErrorKind.PROTOCOL,
                "sbell response exceeded the configured output limit",
                code="SBELL_OUTPUT_TRUNCATED",
            )
        if not result.stdout.strip():
            raise AppError(
                ErrorKind.PROCESS,
                f"sbell returned no response (exit {result.returncode})",
                code="SBELL_NO_RESPONSE",
            )
        try:
            root = ET.fromstring(result.stdout)
        except ET.ParseError as exc:
            raise AppError(
                ErrorKind.PROTOCOL,
                "sbell returned invalid XML",
                code="SBELL_INVALID_XML",
            ) from exc
        status = (root.findtext("status") or "").strip().lower()
        description = root.find("description")
        errno = description.findtext("errno") if description is not None else None
        what = description.findtext("what") if description is not None else None
        action_id = root.findtext("action_id")
        if not status:
            raise AppError(
                ErrorKind.PROTOCOL,
                "sbell response did not contain a status",
                code="SBELL_STATUS_MISSING",
            )
        return SbellResponse(
            status=status,
            action_id=action_id,
            errno=errno,
            what=what,
            description=description,
            returncode=result.returncode,
        )
