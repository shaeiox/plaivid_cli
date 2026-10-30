from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from plaivid_cli.domain.errors import AppError
from plaivid_cli.infrastructure.audit import ReadOnlyAuditAdapter


def _database(path: Path, *, schema: bool = True) -> None:
    connection = sqlite3.connect(path)
    if schema:
        connection.execute(
            "CREATE TABLE Log (time TEXT, user TEXT, user_ip TEXT, product TEXT, message TEXT)"
        )
        connection.executemany(
            "INSERT INTO Log VALUES (?, ?, ?, ?, ?)",
            [
                ("t1", "none", "-", "P", "internal"),
                ("t2", "admin", "10.0.0.1", "P", "Command '/vm/start' has been success"),
                ("t3", "admin", "10.0.0.1", "P", "Command '/vm/stop' has been failed"),
            ],
        )
    connection.commit()
    connection.close()


def test_audit_adapter_is_read_only_and_filters_internal_rows(tmp_path: Path) -> None:
    path = tmp_path / "messages.db"
    _database(path)
    adapter = ReadOnlyAuditAdapter(path)
    entries = adapter.recent(10)
    assert len(entries) == 2
    assert entries[0].command == "/vm/stop"
    assert entries[0].succeeded is False
    assert entries[1].succeeded is True
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    with pytest.raises(sqlite3.OperationalError):
        connection.execute("DELETE FROM Log")
    connection.close()


def test_audit_schema_failure_is_explicit(tmp_path: Path) -> None:
    path = tmp_path / "empty.db"
    _database(path, schema=False)
    with pytest.raises(AppError) as error:
        ReadOnlyAuditAdapter(path).recent()
    assert error.value.code == "AUDIT_SCHEMA_UNSUPPORTED"


def test_audit_limit_is_bounded(tmp_path: Path) -> None:
    adapter = ReadOnlyAuditAdapter(tmp_path / "none.db")
    with pytest.raises(ValueError, match="limit"):
        adapter.recent(10000)
