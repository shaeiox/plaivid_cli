# Tasks (approved; implementation in progress, PVM acceptance pending)

## 1. Evidence and baseline
- [ ] 1.1 Obtain authorized redacted screenshot, installed-version dashboard XML, `nic-list` output/argv, VM running-state contract and VDI source evidence; document unknowns without guessing.
- [ ] 1.2 Capture regression baseline (tests, lint/type/build with supported Python) and current VM operations/shortcuts; set PVM call budget and freshness thresholds with owner.

## 2. Read-only monitoring integration
- [ ] 2.1 Add pure, fixture-backed dashboard parser for verified Host/VM/VDI fields; reject unverified meanings and preserve unavailable/zero distinction.
- [ ] 2.2 Add narrow existing-gateway read support for dashboard query and verified NIC discovery without changing existing action/auth/request formats.
- [x] 2.3 Add bounded local host/NIC read-only collectors with consecutive-sample CPU and throughput rates, safe names, missing/error/reset handling; no Container code.
- [x] 2.4 Extend coordinator sections/health metadata, bounded histories, independent last-good publication and measured latency without affecting operation mutation barriers.

## 3. Scheduling and state
- [x] 3.1 Add one demand-aware Overview scheduler with 3s default, 1–60s validated control, slower PVM cadence, in-flight coalescing and no duplicate loops after navigation/login/logout.
- [ ] 3.2 Add per-collector heartbeat state and tests for success, partial, stale, failed, never-collected and paused states; separate PVM reachability from inferred host power.

## 4. Presentation
- [x] 4.1 Build responsive Overview cards/charts, accurate loading/empty/stale states, interval input and heartbeat detail; no Container section.
- [ ] 4.2 Build physical NIC tabs/details and VM/VDI sections using only verified fields; sample every discovered NIC, not just selected tab.
- [x] 4.3 Make Overview first, Virtual Machines second, retain Audit as secondary access; preserve VM table, UUID selection, detail and all lifecycle actions/shortcuts; update only dirty widgets.
- [ ] 4.4 Review legibility, keyboard focus, text alternatives and 80/120-column/resize behavior against the supplied screenshot (if provided).

## 5. Verification and rollout
- [x] 5.1 Run existing full suite (update navigation assertions without removing tests) plus new fake-provider/parser/scheduler/Textual Pilot tests; check refresh interval, heartbeat, all-NIC sampling, session transitions, lifecycle regression and no screen clearing/flicker.
- [ ] 5.2 Run lint/type/build/security/diff checks; compare actual call counts/latency with approved PVM budget.
- [ ] 5.3 With operator authorization, validate on non-production PVM and update `docs/REAL_PVM_VALIDATION.md`; do not claim real-host acceptance without evidence.
