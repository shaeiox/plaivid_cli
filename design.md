# Plaivid CLI dashboard redesign

## Reference analysis
The supplied reference is a dense, dark, full-terminal VM operations dashboard. It uses a narrow brand/header row with keyboard hints, seven compact host metric cards, a large inventory table on the left, contextual resource/selected-VM/action cards on the right, and command/action/legend panels along the bottom. A saturated blue status strip anchors the bottom edge.

## Visual hierarchy
1. **Header:** product/version and purpose at upper left; Help, Search, Refresh, Quit and local clock at right.
2. **Host summary:** host identity and CPU, RAM, disk, VM count, load and uptime in compact cards.
3. **Inventory:** dominant region; rows show index, state glyph, VM name, state, vCPU, memory, uptime, PID, SPICE port and UUID. Selected row uses a blue highlight where color is available.
4. **Context rail:** resource bars, selected VM facts and available quick actions.
5. **Reference rail:** concise command syntax, VM actions and status legend / counts.
6. **Footer:** connection identity, refresh age and version in a single status bar.

## Implementation guardrails
- Presentation remains in `plaivid_cli/render.py` and styling/glyph policy in `theme.py`; data access, command dispatch and VM action behavior stay untouched.
- Continue accepting existing monitoring and VM model dictionaries; unavailable fields render as `-` rather than triggering new requests.
- Keep the existing text-mode dashboard usable in narrow terminals and when output is piped / `NO_COLOR` is set.
- Make rendering pure and deterministic wherever possible (clock/refresh indicators may be passed in).
- Preserve command-line one-shot output and existing command/page renderers.

## Incremental plan
1. Document reference and isolate presentation from orchestration.
2. Add a dedicated dashboard renderer that assembles summary, inventory, selected VM, actions, command help, legend and footer from current app state.
3. Route only interactive `draw()` through that renderer; preserve all command and action paths.
4. Add renderer-focused regression tests and run the full available test suite / compile checks.
5. Update package version and changelog/docs only after validation; commit/push only when requested/authorized.

## Constraints / differences
The reference depicts live network rates and a selected VM, but those values are not all available on the main screen's current data path. Do not add potentially expensive monitoring calls or alter refresh semantics as part of a visual-only change. Display available host metrics and gracefully omit unavailable network values. The session branch is fixed by the coding environment, so the requested new-branch step cannot be performed.
