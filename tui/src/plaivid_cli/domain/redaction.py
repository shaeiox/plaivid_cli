"""Pure secret redaction for user-visible and diagnostic text."""

from __future__ import annotations

import re

_XML_SECRET = re.compile(
    r"(<(?:password|token|secret|session_token)\b[^>]*>).*?(</(?:password|token|secret|session_token)\s*>)",
    re.IGNORECASE | re.DOTALL,
)
_KEY_VALUE_SECRET = re.compile(
    r"\b(password|token|secret|authorization)\b(\s*[:=]\s*)([^\s,;]+)",
    re.IGNORECASE,
)
_FLAG_SECRET = re.compile(r"(--(?:password|token)\s+)([^\s]+)", re.IGNORECASE)
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")


def redact_text(value: object) -> str:
    """Redact common secret forms before values cross a presentation boundary."""
    text = str(value)
    text = _XML_SECRET.sub(r"\1[REDACTED]\2", text)
    text = _KEY_VALUE_SECRET.sub(r"\1\2[REDACTED]", text)
    text = _FLAG_SECRET.sub(r"\1[REDACTED]", text)
    return _JWT.sub("[REDACTED]", text)
