"""Audit log viewer + analyzer.

PVM logs every action to a SQLite database (``/var/log/pvm/messages.db``,
table ``Log``). Internal monitoring chatter has ``user = 'none'``; user-driven
actions carry the real username and a ``Command '/module/command' has been
<result>`` message. We read that read-only and summarize it.
"""

import os
import re
import sqlite3
from collections import Counter

LOG_DB = os.environ.get("PLAIVID_LOG_DB", "/var/log/pvm/messages.db")

_CMD = re.compile(r"Command '([^']+)' has been (.+?)\.?\s*$")


class LogError(Exception):
    pass


def _connect():
    try:
        return sqlite3.connect("file:%s?mode=ro" % LOG_DB, uri=True, timeout=5)
    except sqlite3.Error as exc:
        raise LogError(str(exc))


def recent(limit=40):
    """Most recent completed user actions (newest first)."""
    con = _connect()
    try:
        rows = con.execute(
            "SELECT time, user, user_ip, product, message FROM Log "
            "WHERE user != 'none' AND message LIKE 'Command %has been %' "
            "ORDER BY rowid DESC LIMIT ?", (limit * 3,)).fetchall()
    except sqlite3.Error as exc:
        raise LogError(str(exc))
    finally:
        con.close()

    out = []
    for time_, user, ip, product, message in rows:
        m = _CMD.search(message or "")
        if not m:
            continue
        result = m.group(2)
        if result.startswith("started"):       # keep terminal events only
            continue
        out.append({"time": time_, "user": user, "ip": ip or "-",
                    "product": product or "-", "cmd": m.group(1),
                    "result": result, "ok": "success" in result})
        if len(out) >= limit:
            break
    return out


def summarize(entries):
    """Aggregate stats over a list of entries."""
    cmds = Counter(e["cmd"] for e in entries)
    users = Counter(e["user"] for e in entries)
    failures = sum(1 for e in entries if not e["ok"])
    span = (entries[-1]["time"], entries[0]["time"]) if entries else (None, None)
    return {"total": len(entries), "top_cmds": cmds.most_common(6),
            "top_users": users.most_common(5), "failures": failures,
            "span": span}
