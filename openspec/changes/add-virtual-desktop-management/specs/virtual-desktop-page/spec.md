# Spec Delta

## ADDED Requirements

### Requirement: Dedicated Desktop navigation
The authenticated Textual TUI SHALL have a Virtual Desktops primary page alongside Overview and Virtual Machines, without replacing their shortcuts, Audit access, login/logout, or VM workflows. The page SHALL follow the existing terminal-aware visual system and expose status in text as well as color.

#### Scenario: Keyboard navigation
- **GIVEN** a valid session and a focused Desktop page
- **WHEN** an operator tabs between search, Refresh, list and detail or uses row arrow keys
- **THEN** focus remains visible, the selected full UUID identifies the Desktop, and existing Overview/VM shortcuts still work

### Requirement: Searchable list and detail
The page SHALL show a name-filtered Desktop list and selected detail, retain full UUID as the internal key, and shorten it only for list display. The list SHALL expose cluster status separately from object enablement and local runtime status; verified OS/vCPU and other known facts SHALL be shown, while unverified or absent Owner, Zone, RAM units and optional fields SHALL show N/A. Search SHALL filter locally without extra server calls.

#### Scenario: Selection across refresh and filter
- **GIVEN** a selected Desktop that remains in the result
- **WHEN** results reorder or a local search filter changes
- **THEN** selection remains bound to the same UUID if visible, otherwise clears or moves explicitly without operating on a different Desktop

#### Scenario: Missing owner/zone mapping
- **GIVEN** a Desktop with a parent ID but no verified `xobj_connection` identity mapping
- **WHEN** the list and detail render
- **THEN** they do not label the ID as a human-readable Zone or invent an Owner

### Requirement: Explicit action scope and accessibility
The page SHALL offer the VM page's Start, Resume, Pause, Stop, Reset and Kill choices for the selected Desktop or an explicit Apply to all Desktops scope. It SHALL warn that Desktop applicability is unverified, require typed confirmation for every action, and keep scope, count and inspectable full target UUIDs accessible by keyboard. A name search SHALL NOT silently restrict all-target scope.

#### Scenario: Select all while filtering
- **GIVEN** a local name filter hiding some rows
- **WHEN** the operator selects Apply to all Desktops
- **THEN** the page says that all unfiltered Desktops are targeted, exposes the full target set for review, and does not dispatch before confirmation

### Requirement: VM page control alignment
The Desktop page SHALL match the VM page's summary-card and Refresh placement and the action-selector, all-target checkbox and Audit-control order and sizing. Name search SHALL remain an additional Desktop control.

#### Scenario: Compare the two pages at narrow and wide widths
- **GIVEN** an 80- or 120-column terminal
- **WHEN** the operator switches between the VM and Desktop pages
- **THEN** matching controls retain the same order and configured dimensions

### Requirement: Responsive refresh states
The page SHALL show loading, empty, partial, stale and failed discovery states, plus a manual Refresh, while using application workers and dirty-widget updates to keep navigation responsive. It SHALL not schedule a per-Desktop request or redraw the full screen for one changed row.

#### Scenario: Slow list read
- **GIVEN** a slow authenticated discovery call
- **WHEN** the operator navigates, searches or quits
- **THEN** the TUI remains responsive and publishes a result only if its session epoch is still current

#### Scenario: Empty list
- **GIVEN** an authenticated successful empty result
- **WHEN** the page renders
- **THEN** it says no Virtual Desktops were returned, rather than showing a stale prior row or an error
