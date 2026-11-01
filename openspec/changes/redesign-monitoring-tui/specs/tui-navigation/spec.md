# Delta for TUI Navigation

## Purpose
Defines the two primary authenticated TUI pages and the preservation of existing VM and secondary audit workflows.

## ADDED Requirements

### Requirement: Overview-first primary navigation
The TUI SHALL open Overview after successful login or session resume and SHALL expose Virtual Machines as the second primary page.

#### Scenario: Resumed session
- **GIVEN** a valid cached session
- **WHEN** the TUI resumes it
- **THEN** Overview is the active page and Virtual Machines is the second primary choice

#### Scenario: Fresh sign-in
- **GIVEN** an operator at the sign-in form
- **WHEN** authentication succeeds
- **THEN** Overview is active without requiring manual navigation

### Requirement: Consistent keyboard page switching
The TUI SHALL provide documented keyboard navigation between both primary pages without swallowing input from a focused form or VM table.

#### Scenario: Switching with keyboard
- **GIVEN** an authenticated operator not editing a field
- **WHEN** they use the documented page-switch shortcut
- **THEN** the corresponding page becomes active with a visible focus indication

#### Scenario: Typing refresh interval
- **GIVEN** the refresh input has focus
- **WHEN** the operator types a page shortcut digit
- **THEN** it edits the input rather than changing pages

### Requirement: Preserve VM operations
The Virtual Machines page SHALL retain the existing UUID-based selection, detail and supported VM lifecycle workflows and their confirmation/admission behavior.

#### Scenario: Operations after navigation
- **GIVEN** an eligible selected VM
- **WHEN** an operator switches from Overview to Virtual Machines and invokes an existing action
- **THEN** the existing operation coordinator applies the same action/policy and targets the same canonical UUID

### Requirement: Preserve secondary Audit access
The TUI SHALL keep the existing read-only Audit view reachable without presenting it as a third primary page.

#### Scenario: Audit unavailable
- **GIVEN** the audit source cannot be read
- **WHEN** the operator opens Audit
- **THEN** an unavailable explanation appears and navigation back to Overview or Virtual Machines still works

### Requirement: No post-logout monitoring
The TUI SHALL stop authenticated Overview monitoring requests when the session ends.

#### Scenario: Logout during a read
- **GIVEN** an Overview read is in flight
- **WHEN** the operator logs out
- **THEN** no new authenticated Overview reads start and an old result cannot appear as fresh data in the next session
