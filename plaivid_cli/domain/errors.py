"""Typed application errors with user-safe messages."""

from __future__ import annotations

from plaivid_cli.domain.models import ErrorKind


class AppError(RuntimeError):
    """An expected failure with stable classification and safe display text."""

    def __init__(
        self,
        kind: ErrorKind,
        message: str,
        *,
        code: str | None = None,
        retryable: bool = False,
    ) -> None:
        self.kind = kind
        self.code = code or kind.value.upper()
        self.retryable = retryable
        super().__init__(message)
