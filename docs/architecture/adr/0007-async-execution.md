# ADR 0007 — Async UI and Blocking PVM Work

- **Status:** Proposed; implementation approach open
- **Date:** 2026-10-30

## Context

Textual has an asynchronous UI/event loop; current PVM adapter calls blocking subprocess `communicate()` with a timeout. Running these calls on the UI loop would freeze input and rendering.

## Proposal

Keep UI event handling responsive by executing blocking local provider calls in a bounded worker thread initially, or adopt asyncio subprocess only after `sudo`/signal/runtime behavior is proven. One collector owns polling and coalesces duplicate reads. Mutations are serialized and produce per-target operation outcomes. Cancellation/timeout of a mutation is an ambiguous outcome until state is refreshed; never automatically retry it.

## Consequences

- Worker isolation preserves the current blocking API for an initial prototype but requires careful subprocess and shutdown cleanup.
- Async subprocess may offer cleaner cancellation but increases adapter/platform complexity.
- UI concurrency does not imply concurrent sbell calls; collection concurrency remains measured and capped.

## Validation required

Use fake processes to test timeouts, descendant cleanup, cancellation, process reaping and app shutdown. Measure PVM behavior before enabling simultaneous reads. Confirm how Textual workers are supervised and reported.
