# Design (proposed; no implementation yet)

## Current boundaries and evidence

- `bootstrap.py` creates one `LocalPvmAdapter`, `CollectionCoordinator`, `OperationCoordinator`, `SessionManager` and application facade. `cli.py` dispatches TTY to `PlaividTui`; no owned SSH session exists. `actions/`, `commands/`, `orchestrator.py`, `monitoring.py`, `render.py` are legacy, excluded from the active package path.
- `tui.py` owns login, tabs (`fleet`, `host`, `audit`), Textual widgets, one app timer, worker-mediated reads, VM selection/details/bulk action controls. Fleet is initially selected. It currently clears/repopulates the VM table on publication; this should be minimized for smooth updates. Audit is read on tab entry/explicit refresh. Login/session resume uses `SessionManager`; lifecycle work calls `OperationCoordinator` and its policy. Preserve these paths.
- `application/collection.py` serializes read requests on one worker; merges the existing batched object inventory with process evidence, coalesces active requests, bounds pending intent, tracks section last-good, timestamps and mutation barriers. Existing `host_status` (`sball/show`) and `host_metrics` (`monitoring/metrics`) are independent. `application/ports.py` describes these narrow calls. `infrastructure/pvm/adapter.py` owns exact local PVM invocation and uses `SbellClient`; `parsers.py` parses the response envelope's description into typed facts. `domain/models.py` represents per-section provenance/quality. Session and operations are separate application boundaries.
- `config.py` defaults `PLAIVID_REFRESH` to 3s; the active timer is created on mount, but widget/page activation drives actual requests. Existing tests use fake providers and Textual Pilot. Baseline here: **104 passed** with Python 3.11.2 in a temporary test venv (package declares >=3.12); no target PVM integration verified. `docs/REAL_PVM_VALIDATION.md` remains pending.
- The user-supplied `pvm_overview_dashboard` query is proposed, not currently implemented or accompanied by real response data. The supplied XML fragments do not prove field semantics for `average`, top lists, `storage_list`, running-state counts or VDI capacity. The repository reference lists `network nic-list` but has no response fixture. Do not claim an installed-host schema from these hints.

## Proposed ownership and dependency direction

```text
Textual page shell / navigation
  -> Overview widgets (cards, charts, NIC tabs, VM/VDI views, interval input)
  -> Virtual Machines view (existing controls and operation flow)
  -> secondary Audit access
    -> application dashboard state + interval/scheduler policy
      -> existing CollectionCoordinator (one read lane; mutation barriers)
        -> narrow read-only gateway methods / local Linux metrics adapter
          -> existing SbellClient/ProcessRunner and pure XML/text parsers
```

Textual components consume immutable snapshots and never invoke commands, parse XML or initiate requests from render methods. Prefer small `presentation/` modules for dashboard, components and navigation; keep VM operation callbacks intact. Add only narrow optional read-only sections/ports needed by the dashboard, preserving old interfaces/callers and CLI behavior. No new runtime dependency is required (Textual/Rich already present). Architectural decisions remain **proposed in this design**; the ADR skill requires explicit separate approval before creating/updating ADR files.

## Navigation, visual system and accessibility

Visual-reference refinement: adapt the [Gemini CLI TUI design guide](https://github.com/cola-runner/awesome-tui-design/blob/master/designs/gemini-cli/DESIGN.md) to Plaivid, not its product branding or agent interaction model. Apply its semantic blue/purple/cyan/green/yellow/pink palette to Textual's native controls and dashboard widgets; use a static blue→purple→rose Plaivid wordmark and rounded panels with borders that reflect real collector health. Keep keyboard shortcuts and focus visible at 80/120 columns. Do not adopt Gemini's 33fps spinner or imply heartbeat success from animation. This is a presentation-only refinement and does not affect collection cadence, authentication, or VM operations.

After successful login or resume, select Overview deterministically. Primary tabs 1 Overview / 2 Virtual Machines support click/Tab and documented number-key shortcuts that do not override focused text entry, VM table, confirmation or existing R/Enter/Q behavior; explicit shortcuts to secondary Audit keep it available. A logout/login cycle resets to Overview and invalidates old page jobs. User actions in Virtual Machines continue to use UUID-keyed table selection, details and bulk operations, without changing their admission/confirmation semantics.

Use a layered dark palette, cyan/blue/purple accents, semantic green/amber/red status, high-contrast text labels and visible focus. Use rounded borders only if terminal supports them; never rely on icon/color alone. Metric cards expose title, value/unit/source/age and compact bar or gauge; charts use only timestamped real samples and state when there are too few. Use a wide arrangement at >=120 columns, stack/wrap at ~80, and scroll vertically for small heights; do not hide required details to force a fixed viewport. Reserve compact headings/labels for narrow terminals. Textual differential widget updates should change only dirty values, not clear the screen or rebuild the tree; throttle decorative pulse, disable or reduce animation when slow/narrow, and honor focus. Preserve loading, valid-empty, unsupported, failed, partial and stale states with explanatory text. No fabricated zeros.

## Verified data plan and source boundaries

| Section | Source / policy | Verification gate |
| --- | --- | --- |
| Host identity / CPU / RAM from dashboard | Exact supplied `user objects` query path via existing SbellClient, using existing token gate; parse only evidenced paths | Redacted installed-version response and host identity mapping |
| Host CPU, memory, load, uptime | Read-only local `/proc/stat`, `/proc/meminfo`, `/proc/loadavg`, `/proc/uptime`, `hostname`; CPU needs two real consecutive counter samples; RAM uses MemTotal and MemAvailable | Verify local machine is the monitored PVM host; on mismatch label as local or suppress host claim |
| VM count | Existing inventory + complete, correlated process evidence or owner-verified running-state mapping; cannot count `host_run_name` | Verified running-state policy, incomplete/conflicted evidence -> N/A/partial |
| VM top CPU/RAM/network | Dashboard XML `vm_top_cpu`, `vm_top_ram`, `vm_top_network`; no per-VM reads | Redacted response plus units, identity and completeness semantics; otherwise unavailable |
| VDI | Inspect dashboard `storage_list` and any true disk-specific lists; if insufficient, inspect existing documented read-only PVM interface | Confirm records are individual VDIs, VM/storage association, units; otherwise VDI card reads N/A. Never call guessed endpoint or treat pools as VDIs |
| Physical NIC discovery | `sbell network nic-list` through existing configured executable/privilege and bounded process runner; initial load/manual rediscovery | Captured schema, supported invocation (`params`/token) and device mapping; do not infer physical from generic interface list |
| Per-NIC counters / link | `/sys/class/net/<validated device>/statistics/{rx,tx}_{bytes,packets,errors,dropped}`, sysfs operstate; optional existing `ethtool -S` for CRC | Reject unsafe/untrusted names, validate selected interface is discovered physical host device, handle missing/permission/rollover/reset; unsupported CRC N/A |

No container metrics, widgets or reserved placeholder. VM disk details currently available on-demand are not proof of global VDI inventory or used/free. Do not introduce individual VM/VDI polling; batch dashboard API responses where verified. Linux reads are bounded read-only local file access; no process-wide `/proc` scan. Display all discovered physical NIC tabs while sampling **all** of them regardless of selection. Throughput uses counter deltas divided by monotonic elapsed seconds; first sample, resets, wrap ambiguity, and non-positive delta time are N/A, not 0. Separate real zero from absent. Keep a bounded deque per real series, with timestamps, and no synthetic backfill.

## Scheduler and heartbeat policy

Own exactly one overview scheduling controller in the application/TUI integration, not one timer per card/tab. Start on authenticated Overview entry, pause page-specific ticks on exit/logout, resume without spawning another controller; in-flight reads may finish but must not republish across a changed session/view generation. Manual refresh also passes through the same coordinator. A validated positive interval control (proposed 1–60 whole seconds, default from `PLAIVID_REFRESH` = 3) changes the controller cadence immediately, while rejected values leave the previous cadence in effect. Do **not** change `Settings.refresh_interval` or the operation freshness/admission policy at runtime: it currently feeds mutation safety; any coordinated policy change would need separate explicit review. Avoid overlapping cycles: skip/coalesce ticks while work is active; never queue one new request per missed tick. Rendering/resize/selection changes never request collection.

At the 3s default, lightweight local host/NIC counters sample each tick; verified batched dashboard VM/VDI calls occur no faster than 15–20s / 15–30s respectively (initial due immediately), inventory may be reused when fresh with explicit running-count age. NIC discovery runs at entry/explicit rediscovery, not every tick. Check the actual read-lane capacity/latencies on a real non-production host before locking those budgets; a user change to the main interval affects local collection cadence, not an uncontrolled increase in expensive PVM request rate. Treat permission/credential failure without fast retries.

For each collector (PVM dashboard, local host, VM inventory/derived monitoring, VDI if independently collected, NIC), retain last attempted/success wall-clock times, monotonic success age and measured attempt-to-response latency; a successful transport alone does not count if response status/payload is invalid. Heartbeat summary is ONLINE only when required, supported collectors have recently succeeded; WARNING when a due source fails, ages beyond its expected cadence plus an agreed grace, or optional data is partial; OFFLINE when required collectors have no successful response beyond an agreed offline threshold (propose `max(3 * cadence, process_timeout + cadence)` per source) or repeatedly fail. A never-collected initial source shows LOADING until its first due attempt/deadline; failed without prior success shows WARNING then OFFLINE at its threshold. Unsupported optional VDI/CRC remains N/A, not a reason for false OFFLINE. If local host reads work but PVM fails, display degraded PVM health, not "host powered off". Timestamp and age are from real successes only; aged last-good values remain visibly STALE even without a fresh failure. Use monotonic time for age, wall time only for formatted timestamp; latency is measured around the actual bounded collection, not visual animation. Pause/leave view should show paused collection, not falsely report live ONLINE; summary refreshes on a low-cost UI clock from stored timestamps (no network call).

## Risks, alternatives and approval dependencies

- Reusing `monitoring/metrics` is lower-risk for already supported fields; `/proc` is only for metrics it cannot truthfully supply or for verified local-host data. Do not replace a working collector wholesale.
- A separate ad hoc timer per widget is tempting but violates coordinator single-flight and can hammer PVM; one demand-aware controller minimizes load. A full-screen custom renderer would regress Textual diff rendering.
- NIC discovery syntax is ambiguous: the new requirement says `sbell network nic-list`, while current `SbellClient` always sends `MODULE COMMAND PARAMS [TOKEN]` and default executable is `sudo sbell`. Resolve with authorized output/argv evidence before adding any invocation. Do not change the existing client command shape for other requests.
- The original request asked for Container monitoring, but its explicit **revised integration specification excludes it**. Honor the revision. Audit is existing functionality and stays secondary; it is not a Container section.
- Screenshot is not available in this workspace. Visual review against it requires the owner to provide it. Full PVM acceptance requires an authorized non-production host and redacted fixtures; otherwise report target acceptance NOT PERFORMED.

## Migration / rollback

Introduce evidence-gated read-only adapters and pure parsers first, then state/cadence/heartbeat, then Overview widgets/navigation; retain old VM UI until Pilot regression passes. Roll back by reverting the UI/read-only additions; no PVM configuration, session file format or durable metrics data migration. Keep the legacy code path excluded, rather than reviving its clearing render loop.
