# Spec Delta

## Purpose

Defines local session handling, secret protection, authorization boundaries, and the unresolved credential-argv risk without assuming unsupported PVM authentication mechanisms.

## ADDED Requirements

### Requirement: Explicit credential-argv risk acknowledgement
The application SHALL disclose that current `sbell` authentication and token use expose sensitive values in process arguments, SHALL NOT claim those values are protected from process inspection, and SHALL require explicit operator acknowledgement before using this transport while the risk is unresolved.

#### Scenario: No risk acknowledgement
- **WHEN** a credentialed PVM operation is requested without explicit acknowledgement of argv exposure
- **THEN** the operation is blocked before launching `sbell` and the diagnostic identifies the unresolved security gate without displaying a secret

### Requirement: No invented credential transport
The application SHALL use only credential-input behavior evidenced by the repository or later verified by the PVM owner, and SHALL NOT assume stdin, environment, file descriptor, or other undocumented `sbell` support.

#### Scenario: Unsupported alternative is configured
- **WHEN** configuration requests a credential transport not verified for the installed PVM interface
- **THEN** startup rejects it without sending credentials

### Requirement: Protected session cache
The application SHALL never persist passwords, SHALL store any retained token only in a user-owned private state location using restrictive permissions and atomic replacement, and SHALL tolerate an unavailable cache without logging secrets.

#### Scenario: Session cache permissions
- **WHEN** a token is cached
- **THEN** the state directory and cache file are created with restrictive user-only permissions where supported and the password is absent from the cache

### Requirement: Session cache path safety
The application SHALL reject cached-token reads through symlinked paths or state directories that are not owned and private to the current user; writes SHALL use an atomic replacement in a private state directory.

#### Scenario: Session file is a symlink
- **WHEN** a cached session path resolves through a symlink
- **THEN** the application refuses to read the token and reports a safe path/permission error

### Requirement: No automatic session eviction
The application SHALL NOT evict another PVM session or automatically log out a session as a recovery side effect.

#### Scenario: PVM session cap is reached
- **WHEN** login reports a session-cap error
- **THEN** the application reports the condition and requests an explicit user-directed recovery rather than selecting a session to delete

### Requirement: Secret-safe diagnostics
The application SHALL redact passwords, tokens, login XML, and secret-bearing command arguments from logs, exceptions, terminal output, and test failure messages.

#### Scenario: Login command fails
- **WHEN** the local login process returns an error containing echoed input
- **THEN** the user sees a safe failure category and no credential value
