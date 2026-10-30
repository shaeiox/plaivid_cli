from __future__ import annotations

import logging

from plaivid_cli.infrastructure.diagnostics import RedactingFilter, redact_text


def test_redact_text_hides_xml_password_and_token_values() -> None:
    text = "<params><password>pass-secret</password><token>jwt-secret</token></params>"
    result = redact_text(text)
    assert "pass-secret" not in result
    assert "jwt-secret" not in result
    assert "[REDACTED]" in result


def test_redact_text_hides_key_value_and_jwt_tokens() -> None:
    text = "password=secret-value token: eyJabc.def.ghi"
    result = redact_text(text)
    assert "secret-value" not in result
    assert "eyJabc" not in result


def test_log_filter_removes_secret_bearing_args_and_exception() -> None:
    record = logging.LogRecord("test", logging.ERROR, __file__, 1, "token=%s", ("secret",), None)
    record.exc_info = (RuntimeError, RuntimeError("password=secret"), None)
    assert RedactingFilter().filter(record)
    assert "secret" not in record.getMessage()
    assert record.exc_info is None
