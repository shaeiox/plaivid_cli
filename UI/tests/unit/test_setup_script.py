from __future__ import annotations

import os
from pathlib import Path

SETUP_SCRIPT = Path(__file__).parents[2] / "scripts" / "setup.sh"


def test_setup_script_has_unix_line_endings_and_executable_mode() -> None:
    content = SETUP_SCRIPT.read_bytes()
    assert b"\r" not in content
    assert os.stat(SETUP_SCRIPT).st_mode & 0o111


def test_setup_script_targets_the_ui_project_and_declared_python_floor() -> None:
    source = SETUP_SCRIPT.read_text(encoding="utf-8")
    assert 'PROJECT_ROOT}/pyproject.toml' in source
    assert "pip install --editable '.[dev]'" in source
    assert 'sys.version_info >= (3, 12)' in source
    assert "plaivid-cli" not in source
    assert "--ignore=tests/smoke.py" not in source
