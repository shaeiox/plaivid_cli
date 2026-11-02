# Proposal

## Why

Plaivid's Textual application exposes Overview and Virtual Machines, but has no dedicated view for Lite Virtual Desktop objects. The operator has supplied a **PVM 7.1.26-verified read-only query** and a representative `pvm_desktop_obj` shape. The operator has now supplied web-client requests for `/vm/stop`, `/vm/pause` and the `vm_start` XML. The repository documents the corresponding `sbell vm` commands and identical params, so the **route and XML shape** are established. The supplied request does not show that its UUID belongs to a `pvm_desktop_obj`, whether the calls succeeded, or the response/status. Discovery and the full VM-style action UI may be designed now; Desktop mutations remain blocked per action until Desktop identity, successful outcomes and action-specific payloads are confirmed and this expanded proposal is approved.

## What Changes

- Add a **Virtual Desktops** primary page to the existing authenticated Textual application, preserving Overview, Virtual Machines, Audit, their shortcuts and the existing session/logout flow. Use the same compact terminal-aware palette, keyboard navigation, loading/empty/error/stale states and dirty-widget refresh pattern.
- Add one batched read through the existing local `SbellClient`/gateway/collection lane using `user objects` with exactly `<params><query>/objects/object/*[type[text()="pvm_desktop_lite_virtual_desktop"]]</query></params>` and the current session token. Parse `pvm_desktop_obj` entries into a separate typed Desktop model, keyed by canonical UUID. No per-Desktop read, login, agent, remote connection or server modification.
- Present a searchable list and selected-Desktop detail. Keep object enablement (`is_enabled`), VM local runtime (`virtual_machine/local_status`) and cluster runtime (`virtual_machine/cluster/cluster_status/status`) distinct. Show optional or unverified values as N/A; do not treat a parent ID as a zone name or an unverified `perm` connection as an owner identity.
- Provide a VM-page-style Desktop action dropdown for **Start, Resume, Pause, Stop, Reset, Kill**, for either the selected Desktop or an explicit **Apply to all Desktops** scope. Full canonical UUIDs, not names/short UUIDs, bind selection, approval and dispatch. An active name filter must never silently limit or expand bulk targets: the bulk control explicitly targets the full unfiltered, current Desktop inventory, with target count/UUIDs inspectable before approval. Keep all actions disabled/guarded until their Desktop-specific protocol evidence is approved.
- **Conditional action integration, not approved for dispatch by this proposal alone:** the supplied `/vm/stop` request and `vm_start` XML body map to existing candidate `sbell vm stop|start` shapes (HTTP `version`/`query` are transport-only; the start URL is missing). `/vm/pause` is a route only; Resume/Reset/Kill lack Desktop examples. Each action independently requires proof that the route/params accept a Lite Desktop UUID and produce a successful response. Preserve VM-style freshness, complete-inventory bulk gating, confirmation, sequential dispatch, stop-on-failure/unknown and post-operation reconciliation, but do not reuse VM inventory gates incorrectly. The read-only page remains useful while actions are blocked.
- Add parser, provider, collection, page-navigation and safe action tests. Target-host acceptance is separate from fake/fixture tests.

## Capabilities

### New Capabilities

- `virtual-desktop-inventory`: batched discovery, typed parser, provenance, optional fields and duplicate/partial handling.
- `virtual-desktop-page`: accessible list, search, selection, details, responsive rendering and refresh.
- `virtual-desktop-operations`: all six VM-style Desktop actions plus selected/all scope, **individually gated** on approved Desktop applicability, payload and result evidence; preserve VM admission/confirmation/outcome semantics.

### Modified Capabilities

- Primary TUI navigation gains Virtual Desktops; VM workflows and Overview remain unchanged. There is no canonical archived spec in `openspec/specs/` yet; reconcile with the pending `redesign-monitoring-tui` navigation delta when archiving.

## Impact

After review, expected areas are `domain/` Desktop types; a pure PVM XML parser; `infrastructure/pvm/adapter.py` and a narrow read port; `application/collection.py` and read service; a Desktop presentation module and `tui.py`; tests, documentation and the existing OpenSpec navigation contract. Existing VM action payloads, risk/approval policy, authentication, monitoring budget, operation semantics and CLI commands must not change accidentally. Every Desktop action requires its own evidence and a safely bound Desktop inventory generation before it can be wired to the existing operation engine. Bulk Desktop actions require an operator-approved positive inventory age bound and a complete current Desktop listing; target IDs must be reviewed, no filtered/hidden selection ambiguity. No implementation, live-server calls or production VM/Desktop changes are part of this proposal.

## Review gates / requested evidence

1. Approve the read-only page, layout/navigation and single batched query. The query is owner-verified on PVM 7.1.26; a **redacted full `sbell` envelope containing multiple `pvm_desktop_obj` entries** is still needed to verify nested optional fields, units, empty result, and the precise `xobj_connection` placement/identity mapping. Until then Owner/Zone display N/A or explicit raw IDs, not guessed names.
2. **Per-action gate:** confirm that the captured UUID is a `pvm_desktop_obj` of type `pvm_desktop_lite_virtual_desktop`, confirm the omitted start URL, and supply redacted Desktop-specific module/command, exact params, successful `<response>` envelope, transitions and permissions **for each requested action** (Start, Resume, Pause, Stop, Reset, Kill) on PVM 7.1.26. Stop body/route and Start body match VM shapes, Pause has only a route, and Resume/Reset/Kill are VM-only repository references; none yet prove Lite Desktop applicability. Never send tokens/passwords or run production mutations for this proposal. An action remains unavailable until its own evidence is reviewed; confirm whether activating it requires a second review after evidence arrives.
3. Approve refresh cadence and request budget (one list read per due cycle, one explicit refresh, no per-row **read** requests), status vocabulary, whether `memory/size` is MB, and whether `perm` and `parent` connections resolve to owner/zone names or only identifiers. Confirm that **Apply to all** means all Desktops in the unfiltered current list, regardless of a name search; no selection by currently visible rows alone.
4. Approve this proposal **before any implementation**. Synthetic tests alone are not real-host acceptance; any non-production PVM validation requires separate operator authorization.

## Later implementation decision (supersedes the earlier dispatch gate)

After the read-only page and default-off attestation implementation, the operator
explicitly requested that a confirmed Desktop action **attempt a call** rather
than return "no action call sent". The UI therefore uses documented candidate
`sbell vm/<action>` shapes after typed review of the selected UUID or the full
unfiltered bulk target set. This is an operator-authorized attempt, **not** proof
that a Lite Desktop accepts the VM commands. The supplied Start capture now
identifies `/sabad-plaivid/vm/start` and its XML body; no successful Lite Desktop
response has been provided for Start or the other actions. No live calls were
made while implementing this change. Keep the complete/fresh Desktop listing,
positive bulk age limit, typed confirmation, serialized dispatch, failure/unknown
stop and reconciliation barriers. Production protocol acceptance remains pending
redacted successful response and state-transition evidence per action.
The Desktop page's control order, sizing and summary/Refresh layout now mirror
the VM page; local name search remains an additional Desktop-only control.
