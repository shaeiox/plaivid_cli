"""Lifecycle intent, outcome, and policy value objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .enums import Action, OperationState, RiskLevel


@dataclass(frozen=True, slots=True)
class ActionPolicy:
    action: Action
    risk: RiskLevel


@dataclass(frozen=True, slots=True)
class PvmReply:
    status: str
    action_id: str | None = None
    errno: str | None = None
    message: str | None = None
    returncode: int = 0


@dataclass(frozen=True, slots=True)
class OperationPlan:
    action: Action
    target_uuids: tuple[str, ...]
    inventory_generation: int
    inventory_succeeded_at: datetime
    is_bulk: bool
    freshness_limit_seconds: float
    created_at: datetime


@dataclass(frozen=True, slots=True)
class TargetOutcome:
    uuid: str
    state: OperationState
    message: str = ""
    dispatched: bool = False
    #: sbell/sabadd error number when the PVM answered with a failure envelope.
    #: Retained so failure scope (target vs. session) is classifiable without
    #: parsing display text.
    errno: str | None = None
    #: Structured application error code (e.g. ``PVM_COMMAND_TIMEOUT``,
    #: ``PROCESS_START_FAILED``) when dispatch raised an ``AppError``.
    code: str | None = None


@dataclass(frozen=True, slots=True)
class OperationResult:
    operation_id: str
    action: Action
    state: OperationState
    targets: tuple[TargetOutcome, ...]
    started_at: datetime
    finished_at: datetime | None = None
    message: str = ""

    @property
    def succeeded_count(self) -> int:
        return sum(target.state is OperationState.SUCCEEDED for target in self.targets)

    @property
    def unknown_count(self) -> int:
        return sum(target.state is OperationState.OUTCOME_UNKNOWN for target in self.targets)
