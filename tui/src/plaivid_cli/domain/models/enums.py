"""Shared state enumerations and PVM identifier normalization."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID


class CollectionStatus(StrEnum):
    NEVER = "never_collected"
    CURRENT = "current"
    PARTIAL = "partial"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"


class Action(StrEnum):
    START = "start"
    STOP = "stop"
    KILL = "kill"
    RESET = "reset"
    PAUSE = "pause"
    RESUME = "resume"


class RiskLevel(StrEnum):
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class OperationState(StrEnum):
    QUEUED = "QUEUED"
    DISPATCHING = "DISPATCHING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    PARTIAL = "PARTIAL"
    CANCELLED_BEFORE_DISPATCH = "CANCELLED_BEFORE_DISPATCH"
    NOT_STARTED = "NOT_STARTED"
    COMMAND_ACCEPTED_UNCONFIRMED = "COMMAND_ACCEPTED_UNCONFIRMED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


class ErrorKind(StrEnum):
    CONFIGURATION = "configuration"
    PROCESS = "process"
    PROTOCOL = "protocol"
    PVM_RESPONSE = "pvm_response"
    AUTHENTICATION = "authentication"
    COLLECTION = "collection"
    POLICY = "policy"
    AUDIT = "audit"
    INTERNAL = "internal"


def canonical_uuid(value: str) -> str:
    """Normalize a UUID to lowercase hyphenated form or reject it."""
    try:
        return str(UUID(value.strip())).lower()
    except (AttributeError, ValueError, TypeError) as exc:
        raise ValueError("invalid UUID") from exc
