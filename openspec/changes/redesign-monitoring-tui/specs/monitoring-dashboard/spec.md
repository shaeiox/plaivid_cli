# Delta for Monitoring Dashboard

## Purpose
Defines an accessible, responsive Overview monitoring experience that represents only real observed data.

## ADDED Requirements

### Requirement: Monitoring-first card layout
Overview SHALL show Host Overview cards for running VMs, CPU, memory, load and heartbeat, followed by host charts, physical NICs, VM monitoring and VDI monitoring in that order.

#### Scenario: Standard terminal
- **GIVEN** an authenticated operator in an 80-column terminal
- **WHEN** Overview renders
- **THEN** every section is reachable in the documented order with readable titles, values and units

#### Scenario: Wide terminal
- **GIVEN** an authenticated operator in a 120-column terminal
- **WHEN** Overview renders
- **THEN** cards use the extra width without hiding or duplicating required sections

### Requirement: Truthful visualizations
Overview SHALL display gauges, bars or charts only for verified metrics and SHALL distinguish actual zero from loading, unavailable, partial, error and stale values in text as well as color.

#### Scenario: Single CPU sample
- **GIVEN** only one host CPU counter sample
- **WHEN** CPU utilization is rendered
- **THEN** no utilization value or fabricated history point is shown

#### Scenario: Failed update after success
- **GIVEN** a previously measured memory value and a failed new collection
- **WHEN** Overview renders
- **THEN** the previous value remains visible with its last success and a stale/error label, not as current

### Requirement: Collection-backed heartbeat display
The heartbeat card SHALL display ONLINE, WARNING or OFFLINE from actual collection health, last successful timestamp and elapsed time, available collection latency, and per-collector status; it SHALL mark expired data stale.

#### Scenario: Successful versus decorative pulse
- **GIVEN** no new successful collection after a prior sample
- **WHEN** a decorative pulse or UI clock advances
- **THEN** the last-success timestamp does not change and the status degrades as its age exceeds policy

#### Scenario: Initial failure
- **GIVEN** a collector has never succeeded
- **WHEN** its first due collection fails
- **THEN** its health is WARNING, progressing to OFFLINE at the approved threshold rather than ONLINE

### Requirement: Dynamic refresh control
Overview SHALL show a refresh interval control at the top, defaulting to 3 seconds, and SHALL apply a valid changed interval to collection scheduling without restart or page exit.

#### Scenario: Operator changes interval
- **GIVEN** the displayed control reads `Refresh: 3s`
- **WHEN** an operator enters a valid 5-second interval
- **THEN** the control reads `Refresh: 5s` and subsequent local Overview collections use that cadence

#### Scenario: Invalid interval
- **GIVEN** a working configured interval
- **WHEN** an operator enters zero, non-numeric input or a value outside the supported range
- **THEN** an explanation appears and the previous scheduler interval remains in effect

### Requirement: NIC tab detail
Overview SHALL present a selectable tab for each discovered physical interface and SHALL display available RX/TX throughput, packets, errors, drops, CRC errors and link state for the selected interface.

#### Scenario: Unsupported CRC
- **GIVEN** an interface with no supported CRC counter
- **WHEN** the tab is selected
- **THEN** CRC is shown as N/A rather than 0

### Requirement: No Container dashboard
Overview SHALL NOT display or reserve a Container monitoring section or collect Container metrics.

#### Scenario: Empty VDI or NIC inventory
- **GIVEN** no verified VDI fields or discovered physical NICs
- **WHEN** Overview renders
- **THEN** the relevant sections explain unavailable or empty state without substituting a Container panel

### Requirement: Smooth keyboard-accessible rendering
The TUI SHALL maintain a visible focus and text status at narrow and wide widths and SHALL update changed widget content without clearing and repainting the entire terminal on each monitoring sample.

#### Scenario: Resize during a slow poll
- **GIVEN** a slow read and an 80-to-120-column resize
- **WHEN** the terminal reflows
- **THEN** input/navigation remain responsive and no full-screen clear or new collection is triggered by the resize
