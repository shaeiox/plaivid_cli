# Spec Delta

## Purpose

Defines the lifecycle and reliability guarantees that let local PVM operations be assembled, configured, bounded, and shut down predictably without coupling core behavior to terminal or subprocess details.

## ADDED Requirements

### Requirement: Single application composition
The application SHALL construct its provider, collection and operation coordinators, and presentation through one composition root, and SHALL stop application-owned work during orderly shutdown.

#### Scenario: Startup and shutdown
- **WHEN** the application starts and later receives a normal shutdown request
- **THEN** one configured application graph is started and its owned workers and child processes are closed or reported unresolved before exit

### Requirement: Configuration validation
The application SHALL validate executable configuration, state paths, and positive process deadlines before starting PVM work, and SHALL report invalid configuration without silently substituting unsafe values.

#### Scenario: Invalid deadline
- **WHEN** the configured process deadline is zero, negative, or not numeric
- **THEN** startup rejects the configuration before launching a child process

### Requirement: Finite timeout and freshness configuration
Process deadlines, refresh intervals, and configured inventory-age limits SHALL be finite and positive; invalid non-finite values SHALL be rejected before process execution or operation admission.

#### Scenario: Infinite inventory age
- **WHEN** the configured inventory-age limit is `inf`, `-inf`, or `nan`
- **THEN** configuration is rejected and freshness checks cannot be bypassed

### Requirement: Bounded local process execution
PVM commands SHALL be launched as argument vectors without shell interpolation, with bounded execution time and output, and every started child SHALL be waited for or explicitly reported as unresolved after cleanup attempts.

#### Scenario: Process timeout
- **WHEN** a fake PVM executable exceeds its configured deadline
- **THEN** the adapter returns a typed timeout result, bounds captured output, and waits/reaps the direct child after cleanup

#### Scenario: POSIX child spawns a descendant
- **WHEN** a fake process tree exceeds its deadline
- **THEN** the isolated process group is terminated and no descendant continues its delayed side effect

#### Scenario: Truncated output
- **WHEN** a child exceeds the retained output limit
- **THEN** the result explicitly carries a truncation signal and downstream parsers do not treat the prefix as complete data

### Requirement: Minimal default child environment
When no explicit trusted environment is configured, child processes SHALL receive only the documented executable lookup, home, and locale variables, not the caller's ambient environment.

#### Scenario: Caller has unrelated secret variables
- **WHEN** a configured command is launched with the default environment policy
- **THEN** unrelated caller secret variables are absent from the child environment

### Requirement: Typed and redacted failures
Expected process, protocol, parsing, policy, and operation failures SHALL retain a stable category and safe diagnostic context without exposing passwords, tokens, login XML, or raw secret-bearing payloads.

#### Scenario: Secret-bearing process error
- **WHEN** a child failure contains credential-bearing input or output
- **THEN** user-facing output and logs contain the failure category and safe operation context but no credential value

### Requirement: No application-owned database
The application SHALL keep current snapshots and bounded in-memory samples in process and SHALL NOT create an application-owned database for monitoring, preferences, or operation history.

#### Scenario: Application restart
- **WHEN** the application exits and is started again
- **THEN** telemetry history is not represented as durable application state
