# Delta for Monitoring Data

## Purpose
Defines evidence-gated, bounded read-only host, VM, VDI and physical-NIC monitoring and truthful collection-health semantics.

## ADDED Requirements

### Requirement: Verified dashboard response
The application SHALL request the specified `user/objects` `/plaivid/overview/pvm_overview_dashboard` read using the existing authenticated invocation path and SHALL parse only verified Host, VM and VDI fields from successful responses.

#### Scenario: Unknown field semantics
- **GIVEN** an installed response with an `average` or `storage_list` whose meaning is unverified
- **WHEN** the dashboard parses it
- **THEN** it does not label that field load average or an individual VDI

#### Scenario: Failed PVM response
- **GIVEN** a PVM rejection or malformed response
- **WHEN** the dashboard read completes
- **THEN** it does not count as a heartbeat success and prior values remain separately marked stale

### Requirement: Honest local host resource rates
The application SHALL calculate local-host CPU utilization from consecutive `/proc/stat` samples and memory utilization from `MemTotal` and `MemAvailable`, while keeping load, uptime and hostname sourced to their local read-only interfaces.

#### Scenario: Counter baseline or missing memory
- **GIVEN** only a baseline CPU sample or absent `MemAvailable`
- **WHEN** host values are published
- **THEN** the affected utilization is unavailable, not zero

### Requirement: Verified running VM count
Overview SHALL calculate running VM count from verified running-state evidence, not from the number of dashboard `host_run_name` elements.

#### Scenario: Incomplete process inventory
- **GIVEN** a partial running-process listing with missing rows
- **WHEN** a VM count is derived
- **THEN** absent rows are not treated as proof of stopped VMs and the count is qualified or unavailable

### Requirement: Verified VM and VDI metrics
Overview SHALL present VM top CPU, RAM and network facts and individual VDI inventory/capacity/use only when their field paths, units and record types have been verified against supported PVM data.

#### Scenario: Storage pools only
- **GIVEN** a dashboard `storage_list` verified to contain only pools
- **WHEN** VDI monitoring renders
- **THEN** it does not call those entries VDIs or invent capacity/usage per disk

### Requirement: Physical NIC discovery and sampling
The application SHALL discover physical interfaces using the verified `sbell network nic-list` contract and SHALL collect independent read-only counters for every discovered physical interface regardless of the selected tab.

#### Scenario: Switch selected NIC
- **GIVEN** two discovered interfaces
- **WHEN** the operator selects the second interface
- **THEN** both interfaces continue to receive timestamped counter samples

### Requirement: Correct NIC rate and availability semantics
The application SHALL compute throughput using consecutive counter differences and actual monotonic elapsed time, and SHALL report missing, unsupported, reset or invalid counters as unavailable rather than zero.

#### Scenario: Reset between samples
- **GIVEN** RX bytes decrease between two samples
- **WHEN** a rate is calculated
- **THEN** RX throughput is N/A for that interval and no negative rate or fabricated history is shown

### Requirement: Independent collection health
The application SHALL track actual attempted and successful timestamps, measured latency and staleness independently for PVM dashboard, host resources, VM evidence, VDI (if separate), and physical NIC collection.

#### Scenario: Host good, PVM down
- **GIVEN** local host reads succeed but the PVM dashboard read fails beyond its due threshold
- **WHEN** the heartbeat is evaluated
- **THEN** the PVM collector is degraded and the summary cannot claim all monitoring is ONLINE or infer that the host is powered off

### Requirement: One bounded refresh schedule
The application SHALL run at most one active Overview scheduling loop, avoid concurrent overlapping collection cycles and bound pending read demand, including after interval changes and page navigation.

#### Scenario: Navigate repeatedly during slow collection
- **GIVEN** a read takes longer than the refresh interval
- **WHEN** an operator leaves and returns to Overview repeatedly
- **THEN** no duplicate scheduler or unbounded pending reads are created

### Requirement: Efficient read-only monitoring
The dashboard SHALL avoid per-VM/VDI polling, refrain from installing software on a PVM host, and avoid re-running NIC discovery or expensive PVM dashboard requests on every lightweight host tick.

#### Scenario: Three-second local interval
- **GIVEN** the default 3-second interval and unchanged NIC inventory
- **WHEN** several local ticks occur before a PVM request is due
- **THEN** no per-VM/VDI commands or repeated NIC discovery are issued
