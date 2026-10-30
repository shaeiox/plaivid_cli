# ADR 0008 — Application Persistence

- **Status:** Proposed; persistence need unresolved
- **Date:** 2026-10-30

## Context

Current session token is stored in JSON; audit records are read from a PVM-owned SQLite DB. No approved app-owned persistent settings, history, cache or operation journal has been identified.

## Proposal

Do not add SQLAlchemy, Alembic or an app database for current snapshots. Keep transient monitoring state in memory. Confirm whether session persistence remains required and select secure storage separately. If a concrete small local preference/cache need is approved, start with stdlib `sqlite3` or a versioned JSON file as appropriate. Introduce SQLAlchemy/Alembic only when schema complexity, query requirements and migration policy justify them.

## Consequences

- Avoids runtime dependency and migration burden without a user need.
- App-owned state is not durable across restarts unless specifically approved.
- Existing PVM audit DB remains an external read-only source and is not migrated or owned by the CLI.

## Validation required

Product decision on persisted preferences/history/session; retention and backup requirements; concurrency/process-count requirements; security review of credential storage.
