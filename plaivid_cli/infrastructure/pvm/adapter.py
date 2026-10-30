"""Infrastructure implementation of the single local PVM gateway."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Sequence
from datetime import UTC, datetime

from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import (
    Action,
    CollectionStatus,
    ErrorKind,
    HostMetrics,
    HostStatus,
    ObjectVM,
    ProcessObservation,
    PvmReply,
    PvmSession,
    SourceResult,
    VMDetail,
    canonical_uuid,
)
from plaivid_cli.infrastructure.diagnostics import redact_text
from plaivid_cli.infrastructure.process import ProcessError, ProcessRunner, ProcessStartError
from plaivid_cli.infrastructure.pvm.parsers import (
    parse_metrics,
    parse_object_inventory,
    parse_process_rows,
    parse_sball_status,
    parse_tap_mapping,
    parse_vm_detail,
)
from plaivid_cli.infrastructure.pvm.sbell import SbellClient, SbellResponse

VM_QUERY = (
    "<params><query>/objects/object/pvm_vmm_obj"
    "[type[text()='pvm_vmm_virtual_machine']]</query></params>"
)
ERRNO_HINT = {
    "39": "session missing or expired",
    "40": "permission denied or malformed request",
    "108": "local sbell permission denied",
    "137": "authentication rejected",
    "146": "VM state rejected by PVM",
    "185": "PVM session limit reached; no sessions were removed",
}


def _xml_text(tag: str, value: str) -> str:
    element = ET.Element(tag)
    element.text = value
    return ET.tostring(element, encoding="unicode", short_empty_elements=False)


def _login_params(username: str, password: str) -> str:
    root = ET.Element("params")
    ET.SubElement(root, "username").text = username
    ET.SubElement(root, "password").text = password
    return ET.tostring(root, encoding="unicode", short_empty_elements=False)


def _action_params(action: Action, uuid: str) -> str:
    key = canonical_uuid(uuid)
    if action is Action.START:
        # This parameter structure is copied from the existing source action.
        return (
            f"<vm_start><vm_key>{key}</vm_key><host>auto</host>"
            "<version_start><version_enable>no</version_enable>"
            "<version_vkey></version_vkey></version_start>"
            "<exit_from_replicate>yes</exit_from_replicate></vm_start>"
        )
    return _xml_text("vm_key", key)


class LocalPvmAdapter:
    """Adapt the repository's existing local commands to typed source values."""

    def __init__(
        self,
        sbell: SbellClient,
        process_runner: ProcessRunner,
        running_vms_argv: Sequence[str],
        *,
        allow_credential_argv: bool = False,
    ) -> None:
        if not running_vms_argv or any(not part for part in running_vms_argv):
            raise ValueError("pvm-running-vms executable must be a non-empty argv")
        self._sbell = sbell
        self._runner = process_runner
        self._running_argv = tuple(running_vms_argv)
        self._allow_credential_argv = allow_credential_argv

    def _call(self, module: str, command: str, params: str = "<params/>", token: str | None = None) -> SbellResponse:
        if token and not self._allow_credential_argv:
            raise AppError(
                ErrorKind.POLICY,
                "sbell token argv exposure requires explicit operator acknowledgement",
                code="CREDENTIAL_ARGV_ACK_REQUIRED",
            )
        try:
            return self._sbell.call(module, command, params, token)
        except ProcessStartError as exc:
            raise AppError(ErrorKind.PROCESS, str(exc), code="PROCESS_START_FAILED") from exc
        except ProcessError as exc:
            raise AppError(ErrorKind.PROCESS, str(exc), code="PVM_PROCESS_ERROR") from exc

    @staticmethod
    def _require_read(response: SbellResponse, operation: str) -> ET.Element:
        if not response.ok:
            details = response.what or ERRNO_HINT.get(response.errno or "") or "PVM rejected the request"
            safe = redact_text(details)
            code = response.errno or "UNKNOWN"
            raise AppError(
                ErrorKind.PVM_RESPONSE,
                f"{operation} failed ({code}): {safe}",
                code=f"PVM_{operation.upper().replace('/', '_')}_FAILED",
            )
        if response.description is None:
            raise AppError(
                ErrorKind.PROTOCOL,
                f"{operation} returned no description",
                code="PVM_DESCRIPTION_MISSING",
            )
        return response.description

    def login(self, username: str, password: str) -> PvmSession:
        if not self._allow_credential_argv:
            raise AppError(
                ErrorKind.POLICY,
                "sbell password argv exposure requires explicit operator acknowledgement",
                code="CREDENTIAL_ARGV_ACK_REQUIRED",
            )
        response = self._call("user", "login", _login_params(username, password))
        if not response.ok:
            details = ERRNO_HINT.get(response.errno or "", "PVM rejected login")
            raise AppError(
                ErrorKind.AUTHENTICATION,
                redact_text(details),
                code=f"PVM_LOGIN_{response.errno or 'FAILED'}",
            )
        token = response.token
        if not token:
            raise AppError(
                ErrorKind.PROTOCOL,
                "login response did not contain a token",
                code="PVM_LOGIN_TOKEN_MISSING",
            )
        return PvmSession(username=username, token=token, authenticated_at=datetime.now(UTC))

    def validate_session(self, session: PvmSession) -> bool:
        response = self._call("user", "whoami", token=session.token)
        return response.ok

    def logout(self, session: PvmSession) -> None:
        response = self._call("user", "logout", token=session.token)
        if not response.ok:
            raise AppError(
                ErrorKind.AUTHENTICATION,
                "PVM logout was rejected",
                code=f"PVM_LOGOUT_{response.errno or 'FAILED'}",
            )

    def list_objects(self, token: str) -> SourceResult[tuple[ObjectVM, ...]]:
        description = self._require_read(
            self._call("user", "objects", VM_QUERY, token), "user/objects"
        )
        return parse_object_inventory(description)

    def list_processes(self) -> SourceResult[tuple[ProcessObservation, ...]]:
        try:
            result = self._runner.run(self._running_argv)
        except ProcessError as exc:
            raise AppError(ErrorKind.PROCESS, str(exc), code="RUNNING_VMS_PROCESS_ERROR") from exc
        if not result.stdout.strip():
            raise AppError(
                ErrorKind.PROCESS,
                f"pvm-running-vms returned no output (exit {result.returncode})",
                code="RUNNING_VMS_NO_OUTPUT",
            )
        parsed = parse_process_rows(result.stdout)
        if result.returncode != 0 or result.stdout_truncated:
            issues = parsed.quality_issues
            if result.stdout_truncated:
                issues += ("running-process output was truncated",)
            reason = (
                f"helper exited with status {result.returncode}"
                if result.returncode != 0
                else "helper output was truncated"
            )
            return SourceResult(
                value=parsed.value,
                status=CollectionStatus.PARTIAL,
                source="pvm-running-vms",
                error=reason,
                quality_issues=issues,
            )
        return parsed

    def host_status(self, token: str) -> SourceResult[HostStatus | None]:
        response = self._call("sball", "show", token=token)
        description = self._require_read(response, "sball/show")
        return parse_sball_status(description)

    def host_metrics(self, token: str) -> SourceResult[HostMetrics | None]:
        response = self._call("monitoring", "metrics", token=token)
        description = self._require_read(response, "monitoring/metrics")
        return parse_metrics(description)

    def vm_detail(self, token: str, uuid: str) -> SourceResult[VMDetail | None]:
        key = canonical_uuid(uuid)
        query = (
            f"<params><query>/objects/object/pvm_vmm_obj[uuid[text()='{key}']]"
            "</query></params>"
        )
        response = self._call("user", "objects", query, token)
        description = self._require_read(response, "user/objects/detail")
        return parse_vm_detail(description, key)

    def tap_mapping(self, token: str) -> SourceResult[dict[str, str]]:
        response = self._call("user", "objects", VM_QUERY, token)
        description = self._require_read(response, "user/objects/tap-map")
        return parse_tap_mapping(description)

    def dispatch_action(self, token: str, action: Action, uuid: str) -> PvmReply:
        response = self._call("vm", action.value, _action_params(action, uuid), token)
        return response.reply()

    def authenticate_argv_warning(self) -> str:
        return "sbell credentials and tokens are passed in process arguments; this is not verified safe"
