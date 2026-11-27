"""Optional, bounded, read-only access to the PVM-owned audit database."""

from __future__ import annotations

import re
import sqlite3
from collections import Counter
from pathlib import Path
from urllib.parse import quote

from plaivid_cli.domain.errors import AppError
from plaivid_cli.domain.models import AuditEntry, AuditSummary, ErrorKind
from plaivid_cli.infrastructure.diagnostics import redact_text

_COMMAND = re.compile(r"Command '([^']+)' has been (.+?)\.?\s*$")
_REQUIRED_COLUMNS = {"time", "user", "user_ip", "product", "message"}


class ReadOnlyAuditAdapter:
    def __init__(self, database: Path) -> None:
        self._database = database.expanduser()

    def recent(self, limit: int = 40) -> tuple[AuditEntry, ...]:
        if limit < 1 or limit > 500:
            raise ValueError("audit row limit must be between 1 and 500")
        uri = f"file:{quote(str(self._database.resolve()))}?mode=ro"
        try:
            connection = sqlite3.connect(uri, uri=True, timeout=5)
        except sqlite3.Error as exc:
            raise AppError(ErrorKind.AUDIT, "audit database is unavailable", code="AUDIT_OPEN_FAILED") from exc
        try:
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(Log)").fetchall()
            }
            if not _REQUIRED_COLUMNS.issubset(columns):
                raise AppError(
                    ErrorKind.AUDIT,
                    "audit database schema is unsupported",
                    code="AUDIT_SCHEMA_UNSUPPORTED",
                )
            rows = connection.execute(
                "SELECT time, user, user_ip, product, message FROM Log "
                "WHERE user != ? AND message LIKE ? ORDER BY rowid DESC LIMIT ?",
                ("none", "Command %has been %", min(limit * 3, 1500)),
            ).fetchall()
        except sqlite3.Error as exc:
            raise AppError(ErrorKind.AUDIT, "audit query failed", code="AUDIT_QUERY_FAILED") from exc
        finally:
            connection.close()

        entries: list[AuditEntry] = []
        for time_value, user, ip, product, message in rows:
            match = _COMMAND.search(message or "")
            if match is None:
                continue
            result = redact_text(match.group(2))
            if result.startswith("started"):
                continue
            entries.append(
                AuditEntry(
                    time=redact_text(time_value or ""),
                    user=redact_text(user or ""),
                    user_ip=redact_text(ip or "-"),
                    product=redact_text(product or "-"),
                    command=redact_text(match.group(1)),
                    result=result,
                    succeeded="success" in result.lower(),
                )
            )
            if len(entries) >= limit:
                break
        return tuple(entries)

    @staticmethod
    def summarize(entries: tuple[AuditEntry, ...]) -> AuditSummary:
        commands = Counter(entry.command for entry in entries)
        users = Counter(entry.user for entry in entries)
        span = (entries[-1].time, entries[0].time) if entries else (None, None)
        return AuditSummary(
            total=len(entries),
            failures=sum(not entry.succeeded for entry in entries),
            top_commands=tuple(commands.most_common(6)),
            top_users=tuple(users.most_common(5)),
            span=span,
        )
