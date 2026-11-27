# ADR 0006 — Semantic Change Detection and Terminal Rendering

- **Status:** Conditional
- **Date:** 2026-10-30 (revised after architecture review)
- **Decision owner:** Application architecture owner for semantic changes; TUI owner for terminal rendering.

## Context and evidence

- **Repository fact:** current dashboard/overview clear and reprint complete screen blocks (`orchestrator.py:81–103`, `commands/overview.py:32–47`).
- **Proposal:** Textual is the conditional TUI candidate (ADR 0001), with its own terminal differential rendering.
- “Change detection” can refer to two different things; these are deliberately separate here.

## Decision

### A. Semantic application change detection

A pure application-level comparison may compare a newly normalized section/snapshot with the prior valid value and publish a typed semantic change only when relevant domain values differ. It may suppress redundant application events, derived calculations, and widget data updates. Equality ignores collection timestamps/status metadata where the underlying value is unchanged, while freshness/status transitions remain meaningful events. This detector operates on domain/application data and has no terminal-cell knowledge.

### B. Terminal-cell differential rendering

If the Textual prototype is accepted, Textual owns invalidation and terminal-cell diff rendering. Presentation updates stable widgets/rows when application state changes. No custom ANSI cell comparison, dirty-region engine, or parallel terminal diff implementation is proposed.

The presentation may repaint a whole screen when navigation, resize, theme, or a framework requires it. “Diff-based” does not mean every application snapshot must result in a minimal number of terminal writes; it means the framework owns terminal rendering and the application avoids needless semantic updates.

## Consequences

- Domain/application change detection remains testable without a terminal.
- Textual rendering optimizations are not duplicated in custom code.
- Stable widget identity, selection preservation and avoiding needless full data-source replacement remain application UI responsibilities.
- The value of a semantic detector must be measured; do not add it if it duplicates Textual's data/update mechanisms without reducing work.

## Validation required

Unit-test semantic changes for stable values, freshness-only transitions, missing/unsupported fields, counter reset, and section-level partial updates. Prototype Textual with realistic tables; profile CPU, memory, table update latency, repaint/flicker and resize. Custom rendering optimization requires measured evidence and a separate review.
