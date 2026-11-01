# Tasks (implementation started; Desktop mutation dispatch remains evidence-gated)

## 1. Evidence and approval
- [x] 1.1 User instructed implementation after reviewing the expanded proposal ("start implement").
- [ ] 1.2 Obtain a redacted PVM 7.1.26 full `user/objects` response with multiple `pvm_desktop_obj` records, an empty result, and representative optional `xobj_connection` nodes; confirm `memory/size` units and Owner/Zone identities. Do not collect tokens/passwords.
- [ ] 1.3 Record an agreed Desktop-list cadence, health/freshness thresholds, UI at 80/120 columns and permitted non-production test environment.
- [ ] 1.4 Confirm the captured UUID is a Lite Desktop; obtain version-matched Desktop-specific module/command, exact XML params, successful response, transitions and permissions separately for **Start, Resume, Pause, Stop, Reset, Kill**. Confirm the missing Start URL; `/vm/pause` supplies no payload/result. Review each `sbell vm` mapping and request separate action approval. Keep every unverified action blocked.

## 2. Read-only data (after proposal approval)
- [x] 2.1 Add separate immutable Desktop type, pure XML parser, missing/invalid/duplicate handling, and synthetic tests; retain independent enablement/local/cluster fields. Redacted real fixture still pending.
- [x] 2.2 Add a narrow `user/objects` gateway read using exactly the supplied query, current session token, existing argv-risk gate and typed errors; prove one request serves all Desktop rows.
- [x] 2.3 Add independent coordinator section and application read service with bounded shared read lane, last-good/provenance, stale/partial distinction and session isolation; leave VM operation barriers unchanged.

## 3. Presentation (after proposal approval)
- [x] 3.1 Add third primary tab, responsive list, local search, Refresh, keyboard navigation, selected detail keyed by full UUID, six-action dropdown and Apply to all Desktops with conspicuous unfiltered scope. Preserve Overview/VM tabs, Audit, logout, focus and existing shortcuts.
- [x] 3.2 Show separate enablement/local/cluster statuses, N/A for unverified Owner/Zone and RAM units, plus loading/empty/partial/stale/error text; update only dirty rows and do not poll per Desktop.
- [x] 3.3 Fake-backed Pilot covers 80/120-column page transition, filtering, UUID selection persistence, manual refresh, logout, session-change read race and selected/all action block.

## 4. Desktop actions (each blocked until its own evidence under item 1.4 and separate approval)
- [x] 4.1 Expose Start/Resume/Pause/Stop/Reset/Kill as disabled or guarded for Desktop targets; prove fake gateway sees **zero** dispatch for each unverified action.
- [ ] 4.2 For each approved action, extend the service with typed Desktop-target generation/freshness/approval and the exact verified route/params; use full UUID, no forged VMRecord or unrelated VM inventory gate. Bulk admission requires a configured positive age limit and complete current Desktop list.
- [ ] 4.3 Verify selected vs **unfiltered all** scope, full ordered UUID set and confirmation, sequential bulk stop-on-definite-failure/unknown, timeout/error classifications, stale/partial admission and post-dispatch list reconciliation without per-Desktop read fan-out; only then enable that action.

## 5. Verification and rollout
- [x] 5.1 Run full unit/Pilot suite, Ruff, Pyright, build and strict OpenSpec validation (132 passing tests); do not conflate fixtures with installed PVM acceptance.
- [ ] 5.2 Update operator docs and manual validation checklist. Conduct only separately authorized non-production PVM read/operation tests; otherwise leave action gate explicitly blocked and report the evidence gap.
