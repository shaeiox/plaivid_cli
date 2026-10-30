# ADR 0009 — Local PVM Provider Boundary and Future Providers

- **Status:** Conditional
- **Date:** 2026-10-30 (revised after architecture review)
- **Decision owner:** Domain/application architecture owner; PVM owner validates interface contracts.

## Context and evidence

- **Repository fact:** current source uses local `sbell` invocations and `pvm-running-vms`; it parses XML/text in transport/domain-facing modules. No remote-node, HTTP or raw socket implementation exists.
- **Repository documentation only:** `docs/SBELL-SABAD.md` describes sabad/raw sockets, but the application does not call them and this review had no target host.
- **Approved scope:** Linux, local PVM only; remote-node connectivity deferred. Cluster awareness is limited to information actually exposed and validated through local interfaces.

## Decision

Define a narrow application port, provisionally `LocalPvmProvider`, for the local PVM use cases that have evidence in current source. A contract should be expressed in domain-neutral typed outcomes, not command strings or XML. Its initial responsibilities are:

- Obtain a logical batch of authorized VM inventory, including the existing all-object query plus the separate running-VM source where required (ADR 0004).
- Obtain the host/local-node metrics and Sball status data actually used by the current UI, with per-section results and timestamps.
- Obtain a selected VM detail on demand.
- Execute the explicitly supported VM operations through typed action requests and typed outcomes, subject to ADR 0012.
- Read other auxiliary data such as license/audit information only if that capability remains approved and its source/access policy is documented.

Infrastructure implements this port and owns local process execution, configured executable validation, argv construction, XML/text parsing, exit/error mapping and resource cleanup. The port returns normalized models and explicit unsupported/partial status. Application use cases own orchestration and call the port; Domain has no PVM protocol or subprocess types; Presentation cannot invoke the port or PVM commands directly. Bootstrap wires a local implementation. Detailed dependency rules are owned by ADR 0011.

### Cluster/quorum capability statement

- **Repository fact:** current parser obtains a first `.//cluster/node` and reads `sball_state` and `node_state` (`monitoring.py:30–40`). `health_report()` treats `sball_state == "quorate"` as the Sball-reported quorum-health signal (`monitoring.py:215–217`).
- **Established interpretation:** `sball_state=quorate` is a valid indication that **Sball reports the cluster as Quorate**. Preserve and display that signal accurately, with its source and collection time.
- **Explicit non-implication:** this signal does **not** prove all cluster nodes are healthy or reachable, and does not prove complete cluster membership is available to the client.
- Complete membership, per-node health, node reachability and independent quorum calculations are not verified by current source or target-host evidence. Represent such data as unavailable/unsupported until a supported local source and schema are validated. Do not label an unknown member set as fully healthy.

### Future remote extension (not current scope)

A future approved provider may implement a compatible normalized port or a separately versioned provider capability. Domain models, application use cases and screens remain transport-neutral. This is only an extension seam: do not create remote connection code, a connection pool, a multi-node scheduler, or a generic provider/plugin framework now.

## Consequences

- PVM-specific details are isolated at an infrastructure boundary; provider-neutral application/domain types can be tested without a host.
- A narrow port is based on current features, not a prediction of every future operation.
- Local cluster data may be partial. Capability coverage is explicit and screens must not infer health beyond source evidence.

## Validation required

Redacted command outputs, supported PVM versions, permissions, exit/error contracts, inventory/detail schema, cluster signal semantics, membership availability, and performance from an authorized target. Test provider contract with a fake. Keep remote provider deferred.
