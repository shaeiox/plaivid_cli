# Spec Delta

## Purpose

Defines reproducible packaging and operator handoff for a Linux-local application while keeping runtime installation isolated and distinguishing local package tests from unperformed host validation.

## ADDED Requirements

### Requirement: Isolated runtime packaging
The project SHALL declare Python 3.12 or later, provide a reproducible installable artifact and entry point, and SHALL NOT replace or modify the system Python installation.

#### Scenario: Install into isolated environment
- **WHEN** an operator installs the application in a user-owned virtual environment
- **THEN** the CLI entry point runs without changing `/usr/bin/python` or system packages

### Requirement: Honest package compatibility
Package validation SHALL report the build environment and SHALL NOT claim target PVM ABI, native-tool, or vendor compatibility without owner-provided evidence.

#### Scenario: Wheel builds in CI environment
- **WHEN** a package artifact is built and installed in the available environment
- **THEN** the report identifies that environment and leaves untested target hosts pending

### Requirement: Deployment and rollback guidance
The project SHALL document user-local installation, configuration, removal, upgrade, artifact integrity, and rollback procedures without requiring an application database or target-host software installation.

#### Scenario: Operator reviews deployment instructions
- **WHEN** an operator follows the deployment documentation
- **THEN** the instructions make no system-Python modification and identify package verification and rollback steps

### Requirement: Owner-run PVM validation plan
The project SHALL provide a manual PVM validation checklist with prerequisites, exact read and lifecycle checks, expected observations, failure indicators, evidence to record, and all unperformed host checks marked `PENDING MANUAL PVM VALIDATION`.

#### Scenario: Real-host validation has not occurred
- **WHEN** the application is delivered without access to a supported PVM host
- **THEN** every host-dependent check remains marked pending and no real-PVM verification is claimed
