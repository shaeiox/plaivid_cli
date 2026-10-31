"""Narrow outbound capabilities required by application use cases."""

from __future__ import annotations

from typing import Protocol

from plaivid_cli.domain.models import (
    Action,
    AuditEntry,
    HostMetrics,
    HostStatus,
    ObjectVM,
    ProcessObservation,
    PvmReply,
    PvmSession,
    SourceResult,
    VMDetail,
)
from plaivid_cli.domain.overview import DashboardSample, LocalHostSample, NicSample, PhysicalNic


class PvmGateway(Protocol):
    def login(self, username: str, password: str) -> PvmSession: ...

    def validate_session(self, session: PvmSession) -> bool: ...

    def logout(self, session: PvmSession) -> None: ...

    def list_objects(self, token: str) -> SourceResult[tuple[ObjectVM, ...]]: ...

    def list_processes(self) -> SourceResult[tuple[ProcessObservation, ...]]: ...

    def host_status(self, token: str) -> SourceResult[HostStatus | None]: ...

    def host_metrics(self, token: str) -> SourceResult[HostMetrics | None]: ...

    def vm_detail(self, token: str, uuid: str) -> SourceResult[VMDetail | None]: ...

    def tap_mapping(self, token: str) -> SourceResult[dict[str, str]]: ...

    def dispatch_action(self, token: str, action: Action, uuid: str) -> PvmReply: ...


class MonitoringGateway(Protocol):
    """Optional read-only extension; existing PvmGateway implementations still work."""

    def dashboard(self, token: str) -> SourceResult[DashboardSample]: ...

    def local_host(self) -> SourceResult[LocalHostSample]: ...

    def physical_nics(self, token: str) -> SourceResult[tuple[PhysicalNic, ...]]: ...

    def nic_samples(self, devices: tuple[PhysicalNic, ...]) -> SourceResult[tuple[NicSample, ...]]: ...

class AuditGateway(Protocol):
    def recent(self, limit: int) -> tuple[AuditEntry, ...]: ...
