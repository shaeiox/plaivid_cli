"""Secret-safe stdlib diagnostics."""

from __future__ import annotations

import logging

from plaivid_cli.domain.redaction import redact_text


class RedactingFilter(logging.Filter):
    """Redact formatted records and suppress exception tracebacks that may leak."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(record.getMessage())
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True


def configure_logging(*, verbose: bool = False) -> logging.Logger:
    logger = logging.getLogger("plaivid")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        handler.addFilter(RedactingFilter())
        logger.addHandler(handler)
    return logger
