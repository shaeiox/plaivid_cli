# Proposal

## Why

The active Textual TUI opens on a VM table and shows host facts as two text panels. It lacks a coherent monitoring-first landing page, a collection-backed heartbeat, physical NIC detail, VM/VDI dashboard evidence, and a live refresh control. This change makes the terminal experience a professional, honest infrastructure dashboard **without replacing VM management or its protected PVM/session/operation behavior**.

## What Changes

- Make **Overview** the first primary page after successful login/session resume and **Virtual Machines** the second. Preserve the VM table, selection, details, bulk actions, audit access, logout, CLI commands, and existing shortcuts. Host monitoring moves into Overview; Audit remains reachable as a secondary view/action, not a third primary page.
- Render Overview as a responsive dark card-based dashboard, in this order: Host Overview (running VMs, CPU, memory, load, heartbeat); host history; physical NIC tabs/details; VM monitoring; VDI monitoring. Include accessible text/status and responsive 80/120-column layouts. No Container section or Container collector.
- Add a collection-backed heartbeat with per-source status/timestamps/age/latency and stale/error handling. A displayed pulse is decorative only and cannot imply a successful response.
- Add a top-of-Overview refresh interval control, default **3 seconds**, that changes scheduling in place without duplicate loops or concurrent cycles. Decouple inexpensive host/NIC samples from slower PVM dashboard/inventory requests.
- Extend *read-only* collection through the existing local gateway/coordinator: use the supplied `user objects` dashboard query **only after confirming its installed-host response contract**, verified VM inventory for running count, Linux host counters, `sbell network nic-list` for physical NIC discovery, and sysfs interface counters. VDI fields and VM top-list units are evidence-gated; unsupported fields show N/A. No per-VM/VDI command fan-out or new production-host software.
- Add parser/collector/scheduler and Textual Pilot tests plus authorized non-production PVM verification steps; keep target-host acceptance separate from local tests.

## Capabilities

### New Capabilities

- `tui-navigation`: primary navigation, secondary Audit access and preservation of VM workflows.
- `monitoring-dashboard`: Overview presentation, responsive rendering, interval control, heartbeat and truthful empty/error/stale states.
- `monitoring-data`: bounded, provenance-aware Host/VM/VDI/NIC acquisition, cadence and health reporting.

### Modified Capabilities

None in the canonical `openspec/specs/` tree (currently empty). The earlier `implement-complete-plaivid-cli` change has unarchived `tui-interface` and `pvm-data-and-monitoring` deltas that describe the *existing* runtime; reconcile these changes when archiving so the new requirements extend, rather than overwrite, those contracts.

## Impact

Proposed later implementation touches Textual presentation, read-only gateway/ports, pure parsers/models, collection scheduling and tests. Existing lifecycle request/payload formats, action admission, authentication/token cache, CLI semantics, and the default-deny credential-argv acknowledgement remain unchanged. The local application does **not** own an SSH connection; it invokes configured local `sbell`/`pvm-running-vms` executables. No new SSH layer is proposed. Dashboard XML, NIC-list fields, VDI semantics and the screenshot mentioned in the request are not present in this checkout; they require owner-provided sanitized evidence/visual reference before field-specific or visual sign-off. No real PVM host was accessed while drafting.

## Review gates

1. Approve two-primary-page navigation with Audit kept as a secondary reachable view.
2. Supply or approve collection of redacted installed-version dashboard XML, `nic-list` output, and VDI read-only contract, plus the referenced screenshot if precise visual fidelity is required.
3. Approve collection-cost/freshness budgets and authorized target PVM test environment. Unverified VM/VDI fields stay unavailable, not invented.
4. Approve this proposal before any implementation. No application code changes are part of this proposal.
