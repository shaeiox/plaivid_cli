# Spec Delta

## Purpose

Defines the interactive terminal experience for local PVM operators, with visible collection state, keyboard navigation, stable selection, and responsive updates through the terminal framework.

## ADDED Requirements

### Requirement: TTY-only interactive application
The application SHALL launch the interactive TUI only when both required input and output streams are terminals; otherwise it SHALL use the explicit one-shot CLI path.

#### Scenario: Standard input is piped
- **WHEN** the application starts with a non-TTY input stream
- **THEN** it does not launch the TUI or begin hidden monitoring polls

### Requirement: Core operator views
The TUI SHALL provide dashboard, VM inventory, host/cluster monitoring, selected VM details, and diagnostics/audit views where their sources are available.

#### Scenario: Audit source is unavailable
- **WHEN** the audit database cannot be read
- **THEN** the audit view presents a typed unavailable message while other views remain usable

### Requirement: Responsive collection and rendering
Blocking local PVM work SHALL run outside the UI event loop, and all visible refresh requests SHALL pass through the single application collection coordinator.

#### Scenario: Slow metrics command
- **WHEN** a metrics request is delayed
- **THEN** navigation and exit remain responsive and the affected view shows visible loading or stale state

### Requirement: Stable navigation state
The TUI SHALL preserve selection and focus by stable VM UUID across refreshes and sorting whenever that UUID remains present.

#### Scenario: Inventory reorders
- **WHEN** refreshed inventory rows change order
- **THEN** the previously selected UUID remains selected instead of selecting a different row by index

### Requirement: Visible polling and freshness
The TUI SHALL poll only while a relevant live view is active, show freshness and collection status, and stop requesting periodic work after leaving that view or exiting.

#### Scenario: User leaves live monitoring
- **WHEN** the user navigates away from a live monitoring view
- **THEN** its periodic refresh requests stop and no screen-owned worker remains active

### Requirement: Inspectable operation confirmation
Before any operation requiring confirmation, the TUI SHALL show the exact action, complete canonical target list, count, inventory status, last-success timestamp, computed age, and freshness limit that the approval covers.

#### Scenario: Large bulk target set
- **WHEN** a bulk operation exceeds the visible viewport
- **THEN** the user can inspect the full target set before confirming and the confirmation remains bound to that set
