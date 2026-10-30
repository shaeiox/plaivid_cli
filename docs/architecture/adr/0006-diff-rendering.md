# ADR 0006 — Diff-Based Rendering

- **Status:** Proposed
- **Date:** 2026-10-30

## Context

Current screens clear the terminal and print full blocks. Proposed rendering is diff-based. Textual itself owns terminal rendering and can manage widget updates; a separate custom dirty tracker would duplicate presentation work.

## Proposal

Use Textual's differential rendering, stable widget identities and targeted widget/row updates. Keep an application-level semantic change detector only to suppress unchanged state events/read-model work. Do not compare terminal cells or implement ANSI dirty regions independently.

## Consequences

- Less custom terminal logic than current implementation.
- Efficient screen output still depends on app update patterns, table implementation, terminal behavior and data volume.
- Full-screen changes/resizes may legitimately repaint.

## Validation required

Measure flicker, repaint volume, CPU, memory, resize behavior and large DataTable updates in target terminals. Add custom optimizations only after profiling identifies a bottleneck.
