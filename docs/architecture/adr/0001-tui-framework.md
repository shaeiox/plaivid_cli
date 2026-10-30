# ADR 0001 — TUI Framework

- **Status:** Conditional
- **Date:** 2026-10-30 (revised after architecture review)
- **Decision owner:** Product/architecture owner; UI technical lead supplies prototype evidence.

## Context and evidence

- **Repository fact:** `plaivid_cli/render.py` formats screens; `orchestrator.py` clears and prints full blocks. No TUI framework dependency or UI test suite is present.
- **Approved constraint:** Linux, local PVM, interactive monitoring/navigation.
- **Proposal:** Textual + Rich is the candidate stack, subject to validation. Target PVM terminal, supported inventory size, memory budget, and package compatibility are not known.

## Decision

Conditionally select Textual for the interactive TUI prototype. Use its Rich rendering integration. Add Rich as a direct dependency only when application code imports its APIs independently of Textual. Textual owns terminal-cell differential rendering; this ADR does not select a custom terminal dirty-region renderer.

This is **not acceptance of Textual for production**. If the acceptance criteria below fail on supported systems, return to architecture review before selecting an alternative.

## Prototype acceptance criteria

The prototype must be exercised with the same screens and provider workload intended for the first release, using representative and agreed upper-bound inventory sizes. It is accepted only if all of the following are demonstrated on the supported terminal/PVM-like Linux matrix:

1. **Input responsiveness:** while a fake or controlled slow provider call is pending, keyboard navigation, resize, and exit remain responsive; provider work does not run on the UI event loop.
2. **Correct state updates:** inventory refresh preserves selection by VM UUID where the VM remains present; added/removed/changed rows and section freshness/errors are presented accurately.
3. **Rendering:** normal updates do not visibly flicker or unnecessarily clear/repaint the whole screen; terminal resize and redraw restore a correct screen.
4. **Large inventory:** table rendering, sorting, filtering, and incremental updates complete within explicit latency and memory budgets approved before the test. No budget is asserted by this ADR because product limits and host measurements are missing.
5. **Terminal behavior:** minimum supported dimensions, keyboard focus/navigation, interruption, terminal restoration, Unicode/ASCII capability, and common supported terminal emulators are tested.
6. **Operational feedback:** long-running work, per-target progress, failures, stale data, and notifications remain understandable and are not lost behind transient messages.
7. **Packaging:** the actual packaged artifact launches and behaves correctly on each supported Linux compatibility baseline.

Record VM counts, command latency, app idle/peak memory, CPU during refresh, table update latency, terminal/version matrix, and repeatable test steps. The architecture owner approves explicit numerical budgets before performance results can constitute a pass.

## Consequences

- Replacing the current input/render loop is a presentation migration, not a small styling change.
- Textual adds widget/event-loop state and requires blocking PVM calls to be isolated in bounded workers (ADR 0007).
- Textual's rendering diff does not remove application-level responsibility for stable widget identity, minimal data churn, or truthful error/staleness display.
- DataTable scalability and PyInstaller compatibility remain measured questions, not framework guarantees.

## Unresolved / evidence required

Supported terminal matrix, VM inventory upper bound, CPU/RSS/latency budgets, target libc/package baseline, and accessibility/navigation requirements. See `README.md` (ADR index) for cross-ADR ownership.
