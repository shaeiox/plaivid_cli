# Spec Delta

## ADDED Requirements

### Requirement: Direct Desktop action attempts
The Desktop page SHALL offer Start, Resume, Pause, Stop, Reset and Kill for selected or all Desktops. Choosing an action SHALL submit using the documented candidate `sbell vm/<action>` shape without a separate confirmation. The page SHALL not portray command acceptance as a verified Desktop state transition; actual Lite Desktop applicability remains unverified.

#### Scenario: Operator selects an action
- **GIVEN** authenticated inventory with an admitted Desktop target
- **WHEN** the operator chooses a lifecycle action
- **THEN** the action is submitted without a confirmation prompt

### Requirement: Bind action attempts to Desktop identity and freshness
An action attempt SHALL use full Desktop UUIDs and the documented candidate command/params. Admission SHALL bind to a current complete Desktop inventory generation, session epoch without forging VM inventory records or adding per-Desktop reads. All-target admission SHALL additionally require a configured positive inventory-age limit and a freshly collected complete Desktop section.

#### Scenario: UUID versus display name
- **GIVEN** a Desktop with a name differing from its UUID
- **WHEN** a Desktop action is dispatched
- **THEN** the candidate payload contains the full UUID, never its name or shortened UUID

#### Scenario: Stale or partial inventory
- **GIVEN** a stale, incomplete or obsolete Desktop listing
- **WHEN** selected or all-target dispatch is requested
- **THEN** admission rejects it before transport

### Requirement: Explicit unfiltered all-target scope
Apply to all Desktops SHALL mean every Desktop in the current unfiltered inventory, not merely visible name-filtered rows. The page SHALL expose the action, target count and inspectable full ordered UUID set before action selection. Dispatch SHALL bind to that set and its inventory generation; empty or ambiguous scope SHALL be rejected.

#### Scenario: Search active during bulk selection
- **GIVEN** a name search hiding some Desktops
- **WHEN** Apply to all Desktops is chosen
- **THEN** the operator can inspect the full unfiltered target set before action selection

#### Scenario: Inventory changed before dispatch
- **GIVEN** a selected target set
- **WHEN** the Desktop inventory generation or freshness changes before dispatch
- **THEN** the prior plan is invalid and zero action calls are sent

### Requirement: Serial bulk and reconciled outcomes
Bulk operations SHALL dispatch sequentially in the existing serialized mutation lane and stop further dispatch on definite failure or unknown outcome, reporting unattempted UUIDs. Accepted commands SHALL not be portrayed as completed state transitions. After accepted or uncertain results, the page SHALL reconcile via a shared-lane Desktop list read without per-object polling or blind retry.

#### Scenario: Failure partway through bulk
- **GIVEN** a multi-Desktop action
- **WHEN** a target fails or its outcome is unknown
- **THEN** later targets are not called and the operator sees succeeded, failed/unknown and unattempted targets

#### Scenario: Accepted command
- **GIVEN** a Desktop action accepted by PVM
- **WHEN** execution ends
- **THEN** a Desktop list refresh shows new observed state separately from command acceptance
