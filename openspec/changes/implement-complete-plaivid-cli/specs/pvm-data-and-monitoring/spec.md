# Spec Delta

## Purpose

Defines the observable contract for collecting local PVM inventory and host information while preserving source provenance, partial failures, freshness, and the distinction between reported Sball state and verified cluster health.

## ADDED Requirements

### Requirement: Separate inventory evidence
The system SHALL treat the `user/objects` defined-object query and `pvm-running-vms` process listing as independent sources, correlating only validated canonical UUIDs without allowing process presence to overwrite object-reported state.

#### Scenario: Object and process state disagree
- **WHEN** a process row conflicts with an object's reported state
- **THEN** both source facts and their collection times remain visible and the combined record is marked as conflicted rather than silently rewritten

### Requirement: Partial process data is not negative evidence
The system SHALL use missing process rows as negative evidence only when the process source is complete. Partial, truncated, failed, or unavailable process results SHALL NOT mark otherwise valid object records as state-disagreed solely because no row was returned.

#### Scenario: Process helper output is truncated
- **WHEN** the helper returns a prefix that contains valid rows but the process runner reports truncation
- **THEN** the process source and derived inventory remain partial and absent rows do not establish process absence

### Requirement: Preserve partial inventory
A successful object inventory SHALL remain publishable when process-list enrichment fails, and a running-process-only row SHALL NOT be fabricated as a defined or actionable VM.

#### Scenario: Enrichment command fails
- **WHEN** `user/objects` succeeds and `pvm-running-vms` fails
- **THEN** the object inventory remains available and the process-evidence section reports its own failure or stale value

### Requirement: Report invalid and duplicate source records
The system SHALL exclude malformed or duplicate canonical UUID records from actionable resolution, retain unaffected valid records, and mark the affected source section partial with a bounded quality diagnostic.

#### Scenario: Duplicate object UUID
- **WHEN** two object records normalize to the same UUID
- **THEN** that UUID is ambiguous and cannot be selected for mutation while unrelated valid inventory rows remain usable

### Requirement: Per-section freshness and last-good retention
Each collected section SHALL expose its own attempt time, success time, freshness and partial/unavailable status, and SHALL retain only its own last-good value when a later collection fails.

#### Scenario: Metrics fail after prior success
- **WHEN** a host-metrics refresh fails after a successful inventory refresh
- **THEN** inventory freshness is unchanged and the metrics section retains its prior value marked stale or unavailable

### Requirement: Bounded coordinated collection
The application SHALL admit reads through one collection coordinator, coalesce identical in-flight reads, bound pending refresh intent, and collect only active-view or explicitly requested sections.

#### Scenario: Duplicate refresh requests
- **WHEN** multiple views request the same logical section while its collection is in flight
- **THEN** they share that in-flight result instead of starting duplicate PVM processes

### Requirement: Honest host and cluster indicators
The system SHALL report only values supplied by supported local responses, distinguish unavailable data from zero, and describe `sball_state=quorate` only as “Sball reports Quorate.”

#### Scenario: Quorate response
- **WHEN** a collected Sball state is `quorate`
- **THEN** the UI may display Sball Quorate but SHALL NOT infer complete membership, universal node health, or reachability

### Requirement: No default process-table scan
The system SHALL NOT perform the existing `/proc` uptime scan as part of default or periodic collection.

#### Scenario: Missing helper uptime
- **WHEN** a process row has no uptime field
- **THEN** the system reports uptime unavailable rather than scanning `/proc`

### Requirement: Evidence-backed field reuse
The system SHALL reuse inventory fields for tap or NIC views only when supported-version fixtures establish that those fields are present and parseable; otherwise it SHALL show the section as unavailable or separately collected.

#### Scenario: Missing tap field
- **WHEN** an inventory response fixture lacks a required tap field
- **THEN** inventory remains valid and tap information is not fabricated
