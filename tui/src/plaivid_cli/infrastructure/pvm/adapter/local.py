"""Local PVM gateway implementation over bounded local process adapters."""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime

from plaivid_cli.domain.desktops import VirtualDesktop
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
from plaivid_cli.domain.overview import DashboardSample, LocalHostSample, NicSample, PhysicalNic
from plaivid_cli.infrastructure.diagnostics import redact_text
from plaivid_cli.infrastructure.local_monitor import LinuxMonitor, sballd_pid_file_present
from plaivid_cli.infrastructure.process import (
    ProcessError,
    ProcessRunner,
    ProcessStartError,
    ProcessTimeout,
)
from plaivid_cli.infrastructure.pvm.overview import parse_dashboard, parse_nic_list
from plaivid_cli.infrastructure.pvm.parsers import (
    parse_metrics,
    parse_object_inventory,
    parse_process_rows,
    parse_sball_status,
    parse_tap_mapping,
    parse_vm_detail,
)
from plaivid_cli.infrastructure.pvm.sbell import SbellClient, SbellResponse
from plaivid_cli.infrastructure.pvm.uptime import sball_uptime_seconds

from .requests import (
    DASHBOARD_QUERY,
    DESKTOP_QUERY,
    ERRNO_HINT,
    SBALLD_STATUS_ARGV,
    VM_QUERY,
    _action_params,
    _login_params,
)


class LocalPvmAdapter:
    """Adapt the repository's existing local commands to typed source values."""

    def __init__(
        self,
        sbell: SbellClient,
        process_runner: ProcessRunner,
        running_vms_argv: Sequence[str],
        *,
        allow_credential_argv: bool = False,
        action_timeout: float = 10.0,
    ) -> None:
        if not running_vms_argv or any(not part for part in running_vms_argv):
            raise ValueError("pvm-running-vms executable must be a non-empty argv")
        if not math.isfinite(action_timeout) or action_timeout <= 0:
            raise ValueError("action_timeout must be finite and positive")
        self._sbell = sbell
        self._runner = process_runner
        self._running_argv = tuple(running_vms_argv)
        self._allow_credential_argv = allow_credential_argv
        self._action_timeout = action_timeout
        self._local_monitor = LinuxMonitor()

    def _call(
        self,
        module: str,
        command: str,
        params: str = "<params/>",
        token: str | None = None,
        *,
        timeout: float | None = None,
    ) -> SbellResponse:
        if token and not self._allow_credential_argv:
            raise AppError(
                ErrorKind.POLICY,
                "sbell token argv exposure requires explicit operator acknowledgement",
                code="CREDENTIAL_ARGV_ACK_REQUIRED",
            )
        try:
            return self._sbell.call(module, command, params, token, timeout=timeout)
        except ProcessStartError as exc:
            raise AppError(ErrorKind.PROCESS, str(exc), code="PROCESS_START_FAILED") from exc
        except ProcessTimeout as exc:
            raise AppError(ErrorKind.PROCESS, str(exc), code="PVM_COMMAND_TIMEOUT") from exc
        except ProcessError as exc:
            raise AppError(ErrorKind.PROCESS, str(exc), code="PVM_PROCESS_ERROR") from exc

    @staticmethod
    def _require_read(response: SbellResponse, operation: str) -> ET.Element:
        if not response.ok:
            details = (
                response.what or ERRNO_HINT.get(response.errno or "") or "PVM rejected the request"
            )
            safe = redact_text(details)
            code = response.errno or "UNKNOWN"
            raise AppError(
                ErrorKind.PVM_RESPONSE,
                f"{operation} failed ({code}): {safe}",
                code=f"PVM_{operation.upper().replace('/', '_')}_FAILED",
                errno=response.errno,
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
                errno=response.errno,
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

    def list_desktops(self, token: str) -> SourceResult[tuple[VirtualDesktop, ...]]:
        from plaivid_cli.infrastructure.pvm.desktops import parse_virtual_desktops

        description = self._require_read(
            self._call("user", "objects", DESKTOP_QUERY, token), "user/objects/desktops"
        )
        return parse_virtual_desktops(description)

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
        query = f"<params><query>/objects/object/pvm_vmm_obj[uuid[text()='{key}']]</query></params>"
        response = self._call("user", "objects", query, token)
        description = self._require_read(response, "user/objects/detail")
        return parse_vm_detail(description, key)

    def tap_mapping(self, token: str) -> SourceResult[dict[str, str]]:
        response = self._call("user", "objects", VM_QUERY, token)
        description = self._require_read(response, "user/objects/tap-map")
        return parse_tap_mapping(description)

    def dashboard(self, token: str) -> SourceResult[DashboardSample]:
        description = self._require_read(
            self._call("user", "objects", DASHBOARD_QUERY, token), "user/objects/dashboard"
        )
        return parse_dashboard(description)

    def local_host(self) -> SourceResult[LocalHostSample]:
        sample = self._local_monitor.host()
        status = (
            CollectionStatus.CURRENT
            if sample.memory_total is not None and sample.load1 is not None
            else CollectionStatus.PARTIAL
        )
        sample = replace(
            sample,
            pvm_uptime_seconds=self._sball_uptime_seconds(),
            sballd_pid_file=sballd_pid_file_present(),
        )
        return SourceResult(sample, status, "local /proc, systemctl sballd")

    def _sball_uptime_seconds(self) -> float | None:
        # Read-only local service status; any failure simply leaves uptime unknown.
        try:
            result = self._runner.run(SBALLD_STATUS_ARGV, timeout=5)
        except ProcessError:
            return None
        return sball_uptime_seconds(result.stdout, datetime.now(UTC))

    def physical_nics(self, token: str) -> SourceResult[tuple[PhysicalNic, ...]]:
        # Same configured local command, privilege and token-argv gate as all reads.
        description = self._require_read(
            self._call("network", "nic-list", token=token), "network/nic-list"
        )
        result = parse_nic_list(description)
        if result.value is None:
            return result
        physical = tuple(item for item in result.value if self._local_monitor.physical(item.name))
        return SourceResult(
            physical, result.status, result.source, quality_issues=result.quality_issues
        )

    def nic_samples(self, devices: tuple[PhysicalNic, ...]) -> SourceResult[tuple[NicSample, ...]]:
        # A NIC-list record is not itself proof of a physical Linux device.
        physical = tuple(item for item in devices if self._local_monitor.physical(item.name))
        samples = self._local_monitor.nics(physical)
        status = (
            CollectionStatus.PARTIAL
            if any(sample.rx_bytes is None or sample.tx_bytes is None for sample in samples)
            else CollectionStatus.CURRENT
        )
        return SourceResult(samples, status, "local sysfs")

    def dispatch_action(self, token: str, action: Action, uuid: str) -> PvmReply:
        response = self._call(
            "vm",
            action.value,
            _action_params(action, uuid),
            token,
            timeout=self._action_timeout,
        )
        return response.reply()

    def is_daemon_alive(
        self, timeout: float = 2.0, *, token: str | None = None
    ) -> bool:
        """Probe ``sballd`` responsiveness with a short bounded deadline."""
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        try:
            if token and self._allow_credential_argv:
                response = self._call(
                    "user", "whoami", "<params/>", token, timeout=timeout
                )
            else:
                response = self._sbell.call(
                    "user", "whoami", "<params/>", None, timeout=timeout
                )
        except (AppError, ProcessError, ValueError):
            return False
        if response.ok:
            return True
        # An unauthenticated or expired-token whoami returns status="failed"
        # with an sballd errno (e.g. 39), proving sballd answered over its
        # socket; errno 108 means sbell could not connect to the UNIX socket.
        return (
            response.status == "failed"
            and response.errno is not None
            and response.errno != "108"
        )

    def authenticate_argv_warning(self) -> str:
        return "sbell credentials and tokens are passed in process arguments; this is not verified safe"
