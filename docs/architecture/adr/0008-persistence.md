# ADR 0008 — Session Credential Storage vs Application Persistence

- **Status:** Deferred (application database); session-storage implementation unresolved
- **Date:** 2026-10-30 (revised after architecture review)
- **Decision owner:** Product/security owner for session lifecycle; application architecture owner for non-secret persistence.

## Context and evidence

- **Repository fact:** `session.py` stores `{username, token, saved_at}` in a JSON file and attempts chmod 0600 after replacement (`session.py:36–59`). A server-side `whoami` check validates the cached token before reuse (`session.py:69–77`).
- **Repository fact:** `logs.py` reads the PVM-owned `messages.db` read-only; this is an external audit source, not an application database.
- **Open requirement:** whether the product should persist session credentials, UI preferences, metric history, or operation records; no app-owned DB use case is approved.

## Decision

Treat these as **separate decisions and data classes**:

1. **Session credential lifecycle:** whether to cache a PVM token, where/how to protect it, expiry/logout semantics, and user consent are security/session concerns. The current JSON cache is repository behavior, **not approval of that storage method**. No session secret may be placed in a general-purpose app database by default. ADR 0012 owns protection requirements and residual-risk review; this ADR records that a storage mechanism remains unresolved.
2. **Application persistence:** current monitoring snapshots and screen state remain in bounded process memory. Do not add SQLAlchemy/Alembic or an app-owned SQLite database without an explicit durable-data use case and retention/security policy. If a small local non-secret setting/cache is approved, evaluate stdlib JSON or `sqlite3` first.
3. **PVM audit database:** remains externally owned and read-only; do not migrate, write, or repurpose it as CLI storage.

## Consequences

- A future decision to eliminate token caching can be made independently of snapshot storage.
- Deferring an app database avoids schema/migration/runtime burden but means no persistent telemetry/history by default.
- Current token file behavior needs a security decision before production acceptance, independent of whether SQLAlchemy is adopted.

## Unresolved / evidence required

Decide whether session reuse is required; credential transport and local user threat model; secure storage available on supported Linux hosts; logout/cache invalidation and concurrent app instances; any non-secret preference/history/operation-journal requirements, retention, backup and schema migration policy.
