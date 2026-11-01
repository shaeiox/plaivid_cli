# Spec Delta

## ADDED Requirements

### Requirement: Independently evidence-gated Desktop actions
The Desktop page SHALL offer Start, Resume, Pause, Stop, Reset and Kill for selected or all Desktops. Each action SHALL remain unavailable for dispatch until its own version-matched Lite Desktop UUID applicability, route, XML params, successful response envelope, permissions and transitions are reviewed and approved. VM-only docs and captured requests are candidate evidence, not proof; approval of one action SHALL NOT enable another.

#### Scenario: Unverified action
- **GIVEN** an authenticated operator and a Desktop with an action lacking approved Desktop protocol evidence
- **WHEN** that action is requested for one or all Desktops
- **THEN** the page explains the block and sends zero action calls

### Requirement: Bind approved actions to Desktop identity and freshness
An approved action SHALL use full Desktop UUIDs and verified command/params. Admission SHALL bind to a current complete Desktop inventory generation, session epoch and applicable confirmation policy without forging VM inventory records or adding per-Desktop reads. All-target admission SHALL additionally require a configured positive inventory-age limit and a freshly collected complete Desktop section.

#### Scenario: UUID versus display name
- **GIVEN** a Desktop with a name differing from its UUID
- **WHEN** an approved action is dispatched
- **THEN** the verified payload contains the full UUID, never its name or shortened UUID

#### Scenario: Stale or partial inventory
- **GIVEN** a stale, incomplete or obsolete Desktop listing
- **WHEN** selected or all-target dispatch is requested
- **THEN** admission rejects it before transport

### Requirement: Explicit unfiltered all-target scope
Apply to all Desktops SHALL mean every Desktop in the current unfiltered inventory, not merely visible name-filtered rows. The page SHALL expose the action, target count and inspectable full ordered UUID set before confirmation. Approval SHALL bind to that set and its inventory generation; empty or ambiguous scope SHALL be rejected.

#### Scenario: Search active during bulk approval
- **GIVEN** a name search hiding some Desktops
- **WHEN** Apply to all Desktops is chosen
- **THEN** the operator can inspect and confirm the full unfiltered target set, or cancel without dispatch

#### Scenario: Inventory changed after approval
- **GIVEN** a confirmed target set
- **WHEN** the Desktop inventory generation or freshness changes before dispatch
- **THEN** the prior approval is invalid and zero action calls are sent

### Requirement: Serial bulk and reconciled outcomes
Approved bulk operations SHALL dispatch sequentially in the existing serialized mutation lane and stop further dispatch on definite failure or unknown outcome, reporting unattempted UUIDs. Accepted commands SHALL not be portrayed as completed state transitions. After accepted or uncertain results, the page SHALL reconcile via a shared-lane Desktop list read without per-object polling or blind retry.

#### Scenario: Failure partway through bulk
- **GIVEN** an approved multi-Desktop action
- **WHEN** a target fails or its outcome is unknown
- **THEN** later targets are not called and the operator sees succeeded, failed/unknown and unattempted targets

#### Scenario: Accepted command
- **GIVEN** an approved Desktop action accepted by PVM
- **WHEN** execution ends
- **THEN** a Desktop list refresh shows new observed state separately from command acceptance
