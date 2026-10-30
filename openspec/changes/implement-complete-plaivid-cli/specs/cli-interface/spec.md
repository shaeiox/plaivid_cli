# Spec Delta

## Purpose

Defines the standalone command-line interface for local PVM inspection and operation, including non-interactive behavior, automation output, and truthful process exit categories.

## ADDED Requirements

### Requirement: One-shot read commands
The CLI SHALL provide explicit one-shot commands for VM inventory, host/cluster status, selected VM detail, and supported read-only diagnostics, and SHALL perform no PVM collection for help, version, or configuration-only commands.

#### Scenario: Help without PVM tools
- **WHEN** the user runs the help command on a machine without PVM executables
- **THEN** help is displayed successfully without launching a PVM process

### Requirement: Non-TTY bounded behavior
A non-TTY CLI invocation SHALL perform at most the collection required for that explicit command and SHALL NOT launch a TUI, sleep for additional samples, or leave a polling worker running.

#### Scenario: Piped inventory request
- **WHEN** inventory is requested with non-TTY output
- **THEN** one bounded inventory request is rendered and the process exits without hidden polling

### Requirement: Human and automation output
The CLI SHALL provide readable human output and a stable machine-readable JSON mode for supported commands, preserving partial, stale, unavailable, and per-target operation details.

#### Scenario: Partial collection in JSON mode
- **WHEN** one read section succeeds and another fails under JSON output
- **THEN** the output contains both the successful data and the failed section status without substituting empty healthy values

### Requirement: Truthful exit categories
One-shot commands SHALL return stable exit categories: verified success `0`, failure `1`, rejected `2`, partial `3`, and unverified outcome `4` (including `OUTCOME_UNKNOWN` and command accepted without verified completion).

#### Scenario: Bulk mutation has unknown target
- **WHEN** any dispatched target has an unknown outcome
- **THEN** the CLI returns exit code `4` and includes the unknown target in output

### Requirement: Fail-closed CLI mutations
The CLI SHALL reject mutations without an explicit action, canonical target set, required fresh inventory, and required action-bound approval; it SHALL never treat non-TTY execution as implicit consent.

#### Scenario: Non-TTY mutation lacks approval
- **WHEN** a mutation is invoked through a pipe without an explicit valid action/target approval
- **THEN** the request is rejected before dispatch with exit code `2`
