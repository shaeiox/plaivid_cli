# ADR 0001 — TUI Framework

- **Status:** Proposed; not accepted
- **Date:** 2026-10-30

## Context

Current `render.py` formats screens and `orchestrator.py` clears/reprints them. Product decisions propose Textual + Rich for keyboard navigation, tables, responsive layout, progress and asynchronous interaction. The project is Linux/Python 3.12+; actual PVM terminal, VM-count, memory, packaging and libc baselines are unknown.

## Proposal

Prototype Textual for the full-screen UI and use its Rich integration. Let Textual own terminal-cell differential rendering. Add direct Rich dependency only if application code imports its APIs independently. Do not implement custom dirty-cell rendering before performance evidence.

## Consequences

- Replaces the custom full-screen loop and likely requires a significant presentation/input migration.
- Adds runtime dependencies, event/widget state, and an async UI lifecycle.
- Requires blocking PVM work to run outside the event loop.
- Provides mature widgets, keyboard events, layout, and UI test facilities, subject to actual behavior.

## Validation required

Prototype the VM table at measured normal and upper-bound inventory sizes; test update churn, focus/selection preservation, narrow-terminal layout, resize, notifications, worker responsiveness, terminal restore after signals, Textual tests, memory/CPU, and PyInstaller packaging on supported PVM-like Linux. Compare a Prompt Toolkit alternative only if command-prompt-first interaction remains a product requirement.
