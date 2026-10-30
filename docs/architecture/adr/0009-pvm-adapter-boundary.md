# ADR 0009 — PVM Adapter Boundary and Future Providers

- **Status:** Proposed; current interface behavior unverified on target
- **Date:** 2026-10-30

## Context

Current `transport.py`, `vms.py`, `monitoring.py` and action helpers know about local sbell commands and XML/text formats. Remote nodes are explicitly deferred. Repository docs also describe sabad and raw sockets but the application does not use them.

## Proposal

Create one application-facing local PVM provider port implemented by a local provider that wraps only verified `sbell` and `pvm-running-vms` calls. Normalize transport-specific payloads to provider-neutral immutable node/cluster/VM snapshot models. Application use cases and screens depend on those normalized models, not XML, argv, or connection type. A future provider can implement the same port only after a separate approved remote-connectivity phase.

## Consequences

- Separates transport/protocol from domain and UI while avoiding speculative remote infrastructure.
- The interface must be narrow and based on real use cases; avoid a generic plugin/provider framework.
- Local interfaces may not reveal all cluster members. Normalized data must report unsupported/partial fields honestly.

## Validation required

Capture redacted local PVM fixtures and confirm command contracts, output schemas, membership/quorum data and PVM version support with owners. Test provider conformance using a fake implementation.
