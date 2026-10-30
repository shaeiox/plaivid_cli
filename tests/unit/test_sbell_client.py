from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from plaivid_cli.domain.errors import AppError
from plaivid_cli.infrastructure.process import ProcessResult, ProcessRunner
from plaivid_cli.infrastructure.pvm.sbell import SbellClient


def _client(tmp_path: Path, body: str) -> SbellClient:
    script = tmp_path / "fake_sbell.py"
    script.write_text(
        "import os, sys\n"
        "open(os.environ['FAKE_CAPTURE'], 'w').write(repr(sys.argv[1:]))\n"
        f"print({body!r})\n"
    )
    env = dict(os.environ, FAKE_CAPTURE=str(tmp_path / "argv.txt"))
    return SbellClient([sys.executable, str(script)], ProcessRunner(timeout=2, env=env))


def test_sbell_call_builds_argv_without_shell_and_parses_response(tmp_path: Path) -> None:
    response = '<response><status>success</status><action_id>42</action_id><description>token-value</description></response>'
    script = tmp_path / "fake_sbell.py"
    capture = tmp_path / "argv.txt"
    script.write_text(
        "import os, sys\n"
        "open(os.environ['FAKE_CAPTURE'], 'w').write(repr(sys.argv[1:]))\n"
        f"print({response!r})\n"
    )
    env = dict(os.environ, FAKE_CAPTURE=str(capture))
    client = SbellClient([sys.executable, str(script)], ProcessRunner(timeout=2, env=env))
    parsed = client.call("user", "login", "<params><password>do-not-log</password></params>")
    assert parsed.status == "success"
    assert parsed.action_id == "42"
    assert "do-not-log" in capture.read_text()
    assert parsed.token == "token-value"


def test_sbell_does_not_put_secrets_in_parse_errors(tmp_path: Path) -> None:
    client = _client(tmp_path, "'<password>secret-value</password>'")
    with pytest.raises(AppError) as error:
        client.call("user", "login", "<params/>")
    assert "secret-value" not in str(error.value)
    assert "secret-value" not in repr(error.value)


def test_sbell_rejects_truncated_xml_before_parsing() -> None:
    class TruncatedRunner:
        def run(self, argv, *, timeout=None):
            return ProcessResult(
                0,
                "<response><status>success</status></response>",
                "",
                True,
                False,
                0.01,
            )

    client = SbellClient(("sbell",), TruncatedRunner())
    with pytest.raises(AppError) as error:
        client.call("user", "objects")
    assert error.value.code == "SBELL_OUTPUT_TRUNCATED"


def test_sbell_rejects_untrusted_command_parts(tmp_path: Path) -> None:
    client = _client(tmp_path, "'<response><status>success</status></response>'")
    with pytest.raises(ValueError, match="command"):
        client.call("user; touch /tmp/not-run", "objects")
