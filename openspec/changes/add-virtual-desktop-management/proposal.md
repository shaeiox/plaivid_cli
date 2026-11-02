# Proposal

## Why

Plaivid's Textual application exposes Overview and Virtual Machines, but has no dedicated view for Lite Virtual Desktop objects. The operator has supplied a **PVM 7.1.26-verified read-only query** and a representative `pvm_desktop_obj` shape. The operator has now supplied web-client requests for `/vm/stop`, `/vm/pause` and the `vm_start` XML. The repository documents the corresponding `sbell vm` commands and identical params, so the **route and XML shape** are established. The supplied request does not show that its UUID belongs to a `pvm_desktop_obj`, whether the calls succeeded, or the response/status. The Desktop page now supports operator-selected command attempts, but successful Lite Desktop action applicability remains unverified.

## What Changes

- Add a **Virtual Desktops** primary page to the existing authenticated Textual application, preserving Overview, Virtual Machines, Audit, their shortcuts and the existing session/logout flow. Use the same compact terminal-aware palette, keyboard navigation, loading/empty/error/stale states and dirty-widget refresh pattern.
- Add one batched read through the existing local `SbellClient`/gateway/collection lane using `user objects` with exactly `<params><query>/objects/object/*[type[text()="pvm_desktop_lite_virtual_desktop"]]</query></params>` and the current session token. Parse `pvm_desktop_obj` entries into a separate typed Desktop model, keyed by canonical UUID. No per-Desktop read, login, agent, remote connection or server modification.
- Present a searchable list and selected-Desktop detail. Keep object enablement (`is_enabled`), VM local runtime (`virtual_machine/local_status`) and cluster runtime (`virtual_machine/cluster/cluster_status/status`) distinct. Show optional or unverified values as N/A; do not treat a parent ID as a zone name or an unverified `perm` connection as an owner identity.
- Provide a VM-page-style Desktop action dropdown for **Start, Resume, Pause, Stop, Reset, Kill**, for either the selected Desktop or an explicit **Apply to all Desktops** scope. Full canonical UUIDs, not names/short UUIDs, bind selection and dispatch. An active name filter must never silently limit or expand bulk targets: the bulk control explicitly targets the full unfiltered, current Desktop inventory, with target count/UUIDs inspectable before action selection. Choosing an action submits directly after target and inventory admission, without another prompt.
- Use the documented candidate `sbell vm/<action>` command shapes for operator-selected Desktop attempts. The captured `/vm/start` path and XML establish a candidate route, not a successful Desktop contract. Preserve current inventory freshness, complete-inventory bulk gating, sequential dispatch, stop-on-failure/unknown and post-operation reconciliation, without a confirmation step or an incorrect VM inventory gate.
- Add parser, provider, collection, page-navigation and safe action tests. Target-host acceptance is separate from fake/fixture tests.

## Capabilities

### New Capabilities

- `virtual-desktop-inventory`: batched discovery, typed parser, provenance, optional fields and duplicate/partial handling.
- `virtual-desktop-page`: accessible list, search, selection, details, responsive rendering and refresh.
- `virtual-desktop-operations`: all six VM-style Desktop actions plus selected/all scope, using candidate VM request shapes; preserve VM admission/outcome semantics.

### Modified Capabilities

- Primary TUI navigation gains Virtual Desktops; VM workflows and Overview remain unchanged. There is no canonical archived spec in `openspec/specs/` yet; reconcile with the pending `redesign-monitoring-tui` navigation delta when archiving.

## Impact

After review, expected areas are `domain/` Desktop types; a pure PVM XML parser; `infrastructure/pvm/adapter.py` and a narrow read port; `application/collection.py` and read service; a Desktop presentation module and `tui.py`; tests, documentation and the existing OpenSpec navigation contract. Existing VM action payloads, risk policy, authentication, monitoring budget, operation semantics and CLI commands must not change accidentally. Every Desktop action uses a safely bound Desktop inventory generation; successful deployed response evidence remains necessary before claiming production applicability. Bulk Desktop actions require an operator-approved positive inventory age bound and a complete current Desktop listing; target IDs must be reviewed, no filtered/hidden selection ambiguity. No live-server calls or production VM/Desktop changes were made while implementing this change.

## Review gates / requested evidence

1. Approve the read-only page, layout/navigation and single batched query. The query is owner-verified on PVM 7.1.26; a **redacted full `sbell` envelope containing multiple `pvm_desktop_obj` entries** is still needed to verify nested optional fields, units, empty result, and the precise `xobj_connection` placement/identity mapping. Until then Owner/Zone display N/A or explicit raw IDs, not guessed names.
2. **Production evidence:** confirm the captured UUID is a Lite Desktop and obtain redacted successful response, transitions and permissions separately for Start, Resume, Pause, Stop, Reset and Kill on PVM 7.1.26. The Start URL is `/sabad-plaivid/vm/start`; Pause has only a route capture, and Resume/Reset/Kill have VM-only references. No action confirmation is requested in the application. Never send tokens/passwords in evidence.
3. Approve refresh cadence and request budget (one list read per due cycle, one explicit refresh, no per-row **read** requests), status vocabulary, whether `memory/size` is MB, and whether `perm` and `parent` connections resolve to owner/zone names or only identifiers. Confirm that **Apply to all** means all Desktops in the unfiltered current list, regardless of a name search; no selection by currently visible rows alone.
4. Approve this proposal **before any implementation**. Synthetic tests alone are not real-host acceptance; any non-production PVM validation requires separate operator authorization.

## Current action-intent policy

The operator selected direct VM and Desktop lifecycle dispatch without extra confirmation. The TUI dropdown and VM CLI submit after canonical UUID, inventory generation and freshness checks; no modal, approval record or `--approve` flag is used. Candidate Desktop `vm/<action>` applicability still requires deployed response evidence for production claims. No live mutation was performed during implementation.
