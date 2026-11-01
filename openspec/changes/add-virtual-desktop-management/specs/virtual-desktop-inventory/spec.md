# Spec Delta

## ADDED Requirements

### Requirement: Single authenticated Lite Desktop discovery
The application SHALL fetch the Lite Virtual Desktop list through the existing local `sbell user objects` integration and active session token, using exactly `<params><query>/objects/object/*[type[text()="pvm_desktop_lite_virtual_desktop"]]</query></params>`. It SHALL fetch all records in one call per due refresh, not one call per Desktop, and SHALL never treat discovery as a mutation.

#### Scenario: Multiple Desktops
- **GIVEN** an authenticated session and a response with multiple `pvm_desktop_obj` elements
- **WHEN** the Desktop page requests a refresh
- **THEN** one `user/objects` call produces the list, with each Desktop keyed by its full canonical UUID

#### Scenario: Missing or rejected session
- **GIVEN** no valid session, denied credential-argv acknowledgement, or a failed Sball envelope
- **WHEN** discovery is attempted
- **THEN** no alternate login flow is invoked, the existing typed error is shown, and no records are fabricated

### Requirement: Separate typed Desktop facts
The parser SHALL accept only `pvm_desktop_obj` entries of type `pvm_desktop_lite_virtual_desktop`, preserve their canonical UUIDs and independently model `is_enabled`, `virtual_machine/local_status`, and `virtual_machine/cluster/cluster_status/status`. It SHALL tolerate missing optional fields, calculate vCPU only with valid positive socket/core/thread parts, and SHALL NOT infer memory units, owner names or zone names without verified evidence.

#### Scenario: Optional values absent
- **GIVEN** a Desktop with a valid UUID and missing OS, CPU, memory, parent, enablement or status fields
- **WHEN** its record is parsed and rendered
- **THEN** known facts remain available, unknown values show N/A, and local/cluster/enablement are not collapsed into one status

#### Scenario: Partial and duplicate results
- **GIVEN** an invalid UUID or repeated UUID in an otherwise readable response
- **WHEN** discovery completes
- **THEN** the ambiguous entry is excluded or flagged, the result is partial with quality issues, and it cannot authorize Desktop mutation

#### Scenario: Empty versus unavailable
- **GIVEN** a valid empty `<objects/>` versus an absent/malformed response
- **WHEN** discovery completes
- **THEN** the first is an empty current list; the second is an explicit error/unavailable result, never a silent zero

### Requirement: Independent collection state
The application SHALL store Desktop discovery in its own section with source, generation, last success, freshness and quality status, without changing VM object inventory, VM admission, or dashboard data. Read requests SHALL share the existing bounded coordinator lane and SHALL NOT be made per object.

#### Scenario: VM inventory is independently partial
- **GIVEN** a successful Desktop listing and a partial VM object listing
- **WHEN** the Desktop page displays results
- **THEN** Desktop records remain visible while VM operations retain their own safety gates
