# Spec Delta

## Purpose

Defines how users inspect, identify, sort, and navigate defined virtual machines while preserving stable UUID identity and avoiding misleading selectors or per-VM collection fan-out.

## ADDED Requirements

### Requirement: Stable VM identity
The system SHALL identify each actionable VM by its validated canonical UUID, independently of display name, row position, or process-list ordering.

#### Scenario: Inventory order changes
- **WHEN** a refreshed inventory sorts VMs differently
- **THEN** selection and operation targets continue to refer to the same canonical UUIDs

### Requirement: Unambiguous selector resolution
The system SHALL resolve exact UUIDs, exact names, unique name prefixes, and displayed indexes, and SHALL reject missing, ambiguous, duplicate, or partially resolved selector sets before any operation is dispatched.

#### Scenario: Bulk selector contains an invalid target
- **WHEN** one target in a comma-separated bulk request cannot be resolved
- **THEN** the entire request is rejected and no valid subset is dispatched

### Requirement: On-demand VM detail
The system SHALL fetch full VM detail only for the selected UUID and SHALL NOT issue one detail query per VM during inventory collection.

#### Scenario: User opens one VM
- **WHEN** a user requests details for a selected VM
- **THEN** one UUID-scoped detail request is made and the detail section exposes its own freshness and errors

### Requirement: Honest inventory fields
The system SHALL render missing, malformed, stale, or unsupported VM fields as unavailable rather than substituting healthy or zero values.

#### Scenario: VM resource field is absent
- **WHEN** a valid VM object has no parseable memory or CPU field
- **THEN** the VM remains visible and the missing field is displayed as unavailable
