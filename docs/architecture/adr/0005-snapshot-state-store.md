# ADR 0005 — Snapshot and State Store

- **Status:** Proposed
- **Date:** 2026-10-30

## Context

Current application state is mutable `App.host` and `App.vms` without timestamps or per-section errors. Failed inventory refresh can replace a valid view with an empty list. No app-owned persistence requirement has been confirmed.

## Proposal

Publish immutable, typed normalized snapshots with section timestamps and explicit success/unavailable/stale/error metadata. Maintain last successful value per section in a bounded in-memory state store; retain it on failed poll and show staleness. Keep only bounded samples required for rates/trends. Do not add SQLite/SQLAlchemy for transient dashboard state.

## Consequences

- Views can distinguish empty data from unavailable/stale data and can derive changes deterministically.
- Snapshot schema and equality semantics need definition; model validation has a measurable cost on large inventories.
- App restart loses transient snapshots unless future requirements approve persistence.

## Validation required

Test partial failures, initial failure, repeated failure, stale ages, concurrent refresh, inventory churn and rate counter resets using a fake provider and deterministic clock. Benchmark candidate immutable/Pydantic representation.
