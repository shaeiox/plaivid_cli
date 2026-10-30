# Spec Delta

## Purpose

Defines safe execution and reporting for the six supported VM lifecycle actions, including complete target validation, confirmation binding, serialized bulk behavior, and uncertainty after dispatch.

## ADDED Requirements

### Requirement: Action-bound confirmation
Any required confirmation SHALL bind the exact lifecycle action, ordered canonical UUID set, and displayed object-inventory generation and freshness; a changed target set or inventory invalidates that confirmation.

#### Scenario: Inventory changes after confirmation
- **WHEN** the inventory generation or canonical target set changes before dispatch
- **THEN** the previous confirmation is rejected and the operation is not dispatched

### Requirement: Action-specific risk prompts
The interface SHALL apply the approved risk policy: Start and Resume require explicit single-target intent and bulk confirmation; Stop, Reset, and Pause require action-specific confirmation for a single target and bulk; Kill requires a strong action-specific confirmation even for one target.

#### Scenario: Kill one VM
- **WHEN** a user requests Kill for one VM
- **THEN** the interface shows a distinct high-risk confirmation naming that exact action and canonical target before dispatch

### Requirement: Fresh inventory admission
Every operation SHALL require a current successful unambiguous object record per target; destructive bulk operations SHALL require complete, non-partial inventory within a configured maximum age, and SHALL be rejected while that age is unset.

#### Scenario: Destructive bulk has no approved age
- **WHEN** a destructive bulk operation is requested without an approved inventory maximum age
- **THEN** the operation is rejected before dispatch

### Requirement: Explicit operation outcomes
The system SHALL preserve per-target and aggregate states for queued, dispatching, running, succeeded, failed, rejected, cancelled-before-dispatch, not-started, accepted-but-unconfirmed, and outcome-unknown work.

#### Scenario: Dispatch times out
- **WHEN** a lifecycle command times out after dispatch and completion cannot be established
- **THEN** that target and the aggregate report `OUTCOME_UNKNOWN`, not success or definite failure

### Requirement: Bulk stop on first uncertain or failed result
Bulk operations SHALL run sequentially in the confirmed UUID order, stop after the first definite failure, rejection, or unknown result, and mark every remaining target `NOT_STARTED`. A positive-looking response whose acceptance semantics are unverified is unknown and MUST stop the sequence.

#### Scenario: First target outcome is unknown
- **WHEN** the first target in a bulk request has an unknown post-dispatch result
- **THEN** no later target is dispatched and all remaining targets are reported `NOT_STARTED`

#### Scenario: First target is accepted but unconfirmed
- **WHEN** the first target returns a positive-looking response without a verified acceptance contract
- **THEN** its result is `OUTCOME_UNKNOWN`, no later target is dispatched, and every remaining confirmed target is `NOT_STARTED`

### Requirement: Acceptance is not completion
The system SHALL report command acceptance separately from operation completion and SHALL report success only when a verified contract or approved readback confirms the requested terminal state.

#### Scenario: Successful envelope without verified completion contract
- **WHEN** a command response is positive but completion semantics are unverified
- **THEN** the result remains accepted-but-unconfirmed unless approved readback verifies the terminal state

### Requirement: Truthful aggregate outcome precedence
Aggregate results SHALL preserve the most safety-significant per-target state: `OUTCOME_UNKNOWN` takes precedence over accepted-unconfirmed and definite failures; accepted-unconfirmed takes precedence over definite failures when no target is unknown; mixed confirmed success with definite failure or not-started targets is `PARTIAL`.

#### Scenario: Unknown mixed with failure
- **WHEN** a bulk result contains both `OUTCOME_UNKNOWN` and a definite failure
- **THEN** the aggregate is `OUTCOME_UNKNOWN`

#### Scenario: Accepted-unconfirmed mixed with failure
- **WHEN** a result contains an evidence-backed accepted-unconfirmed target and a definite failure, with no unknown target
- **THEN** the aggregate remains `COMMAND_ACCEPTED_UNCONFIRMED`

### Requirement: No blind retry and ordered reconciliation
The system SHALL NOT automatically retry a lifecycle command after dispatch uncertainty, and SHALL prevent a pre-mutation read for an affected UUID from overwriting newer post-operation state.

#### Scenario: Stale read completes after operation
- **WHEN** a read started before a mutation completes after the operation generation changes
- **THEN** its result is rejected from publication for affected UUIDs
