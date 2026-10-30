# Spec Delta

## Purpose

Defines safe diagnostics and optional access to the PVM-owned audit database, so operators can understand collection and operation outcomes without leaking secrets or treating unavailable logs as application failure.

## ADDED Requirements

### Requirement: Redacted diagnostics
Diagnostics SHALL include safe operation/category/source/timing context and SHALL omit credentials and unreviewed raw PVM payloads.

#### Scenario: Parser rejects secret-bearing response
- **WHEN** a response cannot be parsed and contains a token or password
- **THEN** diagnostics identify a parse failure without printing the raw payload or secret

### Requirement: Read-only audit access
If audit-log viewing is enabled, the application SHALL open the externally owned PVM audit database read-only, use bounded query limits, and report access or schema failures explicitly.

#### Scenario: Audit schema is incompatible
- **WHEN** the configured audit database lacks the expected table or columns
- **THEN** the audit feature reports unsupported/unavailable status without modifying the database

### Requirement: Audit refresh is user-demanded
The TUI SHALL read audit data on tab entry or explicit refresh only; the generic live-view timer SHALL NOT periodically poll the audit database.

#### Scenario: Audit tab remains open
- **WHEN** the user leaves the Audit tab open across refresh intervals
- **THEN** no additional audit query occurs unless the user explicitly refreshes or re-enters the tab

### Requirement: Audit data remains external
The application SHALL NOT copy or migrate PVM audit records into an application-owned database or alter source retention.

#### Scenario: User requests audit history
- **WHEN** the user opens the audit view
- **THEN** records are read from the configured PVM source and no application database is created

### Requirement: Operation result diagnostics
Operation diagnostics SHALL preserve per-target state, safe failure category, and aggregate counts, including `NOT_STARTED` and `OUTCOME_UNKNOWN`.

#### Scenario: Bulk operation stops early
- **WHEN** a bulk operation stops after an uncertain target result
- **THEN** diagnostics report the uncertain target and the remaining not-started targets without falsely reporting overall success
