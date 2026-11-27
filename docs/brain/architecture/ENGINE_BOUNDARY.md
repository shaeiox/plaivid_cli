# TUI / PVM Control Engine boundary (work in progress)

Canonical Engine implementation is being moved into `pvm_control_engine/`; the UI distribution source is under `tui/src/plaivid_cli/`. The intended boundary is structured, versioned JSON-RPC 2.0 over a restrictive Unix-domain socket only. There is no HTTP, `sabad`, or direct raw `sballd` IPC.

Current status: Engine-owned composition, local socket server, allowlisted dispatcher, bounded framing/workers, UID peer checks, structured DTO serialization, operation planning, and the TUI-side socket transport/one-shot CLI exist. The Textual dashboard has not been migrated and remains coupled to its copied application/session/operation code. Therefore this document does not assert runtime import isolation, full feature parity, or independent installation validation. See `docs/PVM_CONTROL_ENGINE.md` for the method list, launch instructions, session-sharing caveat, and verification limitations.
