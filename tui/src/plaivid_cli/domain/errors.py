"""Typed application errors with user-safe messages."""

from __future__ import annotations

from plaivid_cli.domain.models import ErrorKind


class AppError(RuntimeError):
    """An expected failure with stable classification and safe display text.

    ``errno`` carries the ``sbell``/sabadd error number when the failure came
    from a PVM response, so callers can classify *who* the error belongs to
    (one target vs. the whole session) without parsing the message text.
    """

    def __init__(
        self,
        kind: ErrorKind,
        message: str,
        *,
        code: str | None = None,
        retryable: bool = False,
        errno: str | None = None,
    ) -> None:
        self.kind = kind
        self.code = code or kind.value.upper()
        self.retryable = retryable
        self.errno = errno
        super().__init__(message)
