# Tasks (implementation started; confirmed Desktop attempts use candidate routes; production acceptance pending)

## 1. Evidence and approval
- [x] 1.1 User instructed implementation after reviewing the expanded proposal ("start implement").
- [ ] 1.2 Obtain a redacted PVM 7.1.26 full `user/objects` response with multiple `pvm_desktop_obj` records, an empty result, and representative optional `xobj_connection` nodes; confirm `memory/size` units and Owner/Zone identities. Do not collect tokens/passwords.
- [ ] 1.3 Record an agreed Desktop-list cadence, health/freshness thresholds, UI at 80/120 columns and permitted non-production test environment.
- [ ] 1.4 Confirm the captured UUID is a Lite Desktop; obtain version-matched Desktop-specific module/command, exact XML params, successful response, transitions and permissions separately for **Start, Resume, Pause, Stop, Reset, Kill**. The Start URL is now supplied as `/sabad-plaivid/vm/start`; `/vm/pause` supplies no payload/result. Review each `sbell vm` mapping and request separate action approval. Record successful response evidence before treating any action as a verified production contract.

## 2. Read-only data (after proposal approval)
- [x] 2.1 Add separate immutable Desktop type, pure XML parser, missing/invalid/duplicate handling, and synthetic tests; retain independent enablement/local/cluster fields. Redacted real fixture still pending.
- [x] 2.2 Add a narrow `user/objects` gateway read using exactly the supplied query, current session token, existing argv-risk gate and typed errors; prove one request serves all Desktop rows.
- [x] 2.3 Add independent coordinator section and application read service with bounded shared read lane, last-good/provenance, stale/partial distinction and session isolation; leave VM operation barriers unchanged.

## 3. Presentation (after proposal approval)
- [x] 3.1 Add third primary tab, responsive list, local search, Refresh, keyboard navigation, selected detail keyed by full UUID, six-action dropdown and Apply to all Desktops with conspicuous unfiltered scope. Preserve Overview/VM tabs, Audit, logout, focus and existing shortcuts.
- [x] 3.2 Show separate enablement/local/cluster statuses, N/A for unverified Owner/Zone and RAM units, plus loading/empty/partial/stale/error text; update only dirty rows and do not poll per Desktop.
- [x] 3.3 Fake-backed Pilot covers 80/120-column page transition, filtering, UUID selection persistence, manual refresh, logout, session-change read race and selected/all confirmation and no dispatch on cancel.

## 4. Desktop actions (operator-confirmed attempts; deployed success evidence pending)
- [x] 4.1 Expose Start/Resume/Pause/Stop/Reset/Kill as disabled or guarded for Desktop targets; prove fake gateway sees **zero** dispatch before typed confirmation or on rejected admission.
- [x] 4.2 Implement separate typed Desktop-target generation/freshness/approval and candidate documented `sbell vm` route/params; use full UUID, no forged VMRecord or unrelated VM inventory gate. Bulk admission requires a configured positive age limit and complete current Desktop list. Operator now requests confirmed attempts without the prior environment attestation; real Desktop response evidence remains pending.
- [x] 4.3 Synthetic tests cover selected vs **unfiltered all**, typed confirmation, sequential stop-on-failure/unknown, stale/partial admission and list reconciliation without per-Desktop reads. Operator-approved attempts are enabled; production acceptance still requires real Desktop response evidence.

## 5. Verification and rollout
- [x] 5.1 Run full unit/Pilot suite, Ruff, Pyright, build and strict OpenSpec validation (144 passing tests after UI parity and confirmed-attempt update); do not conflate fixtures with installed PVM acceptance.
- [ ] 5.2 Update operator docs and manual validation checklist. Conduct only separately authorized non-production PVM read/operation tests; otherwise report the evidence gap and do not claim production applicability.
