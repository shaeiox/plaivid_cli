from __future__ import annotations

import os
from pathlib import Path

SETUP_SCRIPT = Path(__file__).parents[2] / "scripts" / "setup.sh"


def test_setup_script_has_unix_line_endings_and_executable_mode() -> None:
    content = SETUP_SCRIPT.read_bytes()
    assert b"\r" not in content
    assert os.stat(SETUP_SCRIPT).st_mode & 0o111
