# Proposal

## Why

The current application combines authentication, synchronous PVM calls, mutable data, terminal input, and action dispatch in one legacy orchestrator, with no automated regression suite or package metadata. A single end-to-end redesign is needed to make local PVM management safer, testable without a host, usable from both CLI and TUI, and honest about source freshness and uncertain operation outcomes.

## What Changes

- Replace the legacy command loop/custom terminal renderer with a modular-monolith application and Textual TUI, retaining a practical one-shot CLI.
- Add typed domain models, a single Bootstrap composition root, one CollectionCoordinator and one OperationCoordinator, narrow local PVM ports/adapters, bounded process execution, per-section snapshots, and explicit operation results.
- Integrate only existing local `sbell` and `pvm-running-vms` interfaces and currently supported read/action calls; isolate unverified contracts and do not invent commands or semantics.
- Deliver inventory, selected-VM details, host/Sball monitoring, available network/storage facts, read-only audit logs where permission/schema permit, and all six VM lifecycle actions with fail-closed targeting and confirmation.
- Add fake executables, fixture-backed parser and application tests, CLI/Textual tests, package metadata, packaging checks, user documentation, and owner-run `docs/REAL_PVM_VALIDATION.md`.
- **BREAKING:** non-TTY operations never inherit implicit confirmation; ambiguous/partial selectors reject the complete bulk request; automatic session eviction is disabled; successful PVM command acknowledgement is not reported as completion without verified evidence.
- Real-host authentication and release remain gated by the unresolved credential-in-argv exposure; no undocumented credential channel is assumed. No real PVM access or validation is performed by this change.

## Capabilities

### New Capabilities
- `application-runtime`: composition, configuration, bounded workers/processes, typed results/errors, and orderly shutdown.
- `pvm-data-and-monitoring`: local PVM adapters; source-separated VM inventory; freshness/partial/last-good collection; host, Sball, network, and storage monitoring.
- `vm-management`: VM list/detail models, safe selector resolution, sorting/navigation data, and supported read-only per-VM information.
- `vm-operations`: safe single and bulk start/stop/kill/reset/pause/resume with per-target and aggregate outcomes.
- `cli-interface`: one-shot human/automation commands, no hidden non-TTY polling, and stable truthful exit categories.
- `tui-interface`: Textual dashboard, inventory, monitoring, details, diagnostics, interaction, focus/selection retention, and visible progress.
- `sessions-and-security`: credential/session handling, redaction, privilege boundaries, authorization assumptions, and fail-closed behavior.
- `diagnostics-and-audit`: safe diagnostic reporting and optional read-only PVM audit-log access with visible unavailability.
- `packaging-and-deployment`: supported Python/package entry points, isolated install/removal, offline deployment, and rollback guidance.

### Modified Capabilities

None. `openspec list --specs` found no existing capability specs; all nine capabilities above are new.

## Impact

Affected code: `plaivid_cli/` and existing entry point `plaivid`; tests and fixtures under `tests/`; project packaging/dependency metadata; README and operational documentation; one OpenSpec Change under `openspec/changes/implement-complete-plaivid-cli/`. Runtime PVM commands remain local. No target PVM configuration, system Python, remote collector, or application database is changed or introduced. Host/vendor contracts, target ABI/package compatibility, and operational thresholds remain explicitly pending owner validation.
