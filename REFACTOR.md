# Refactor: command registry (plugin-ize the TUI verbs)

Goal: adding a feature = **drop one file** in `commands/` (a TUI verb) or
`actions/` (a per-VM operation). Dispatch, Tab completion and help are all
derived from the two registries - the orchestrator never needs editing to add
behavior.

Done incrementally; the app stays runnable after every step.

## Design

- `commands/` package mirrors `actions/`: a registry imports each file in its
  own try/except, records `load_errors`, and skips a broken file.
- A command file declares: `NAME`, `ALIASES`, `USAGE`, `DESCRIPTION`, `ORDER`,
  and `run(ctx, args) -> CONTINUE | EXIT`.
- `CommandContext` (facade) gives a command a stable, narrow API onto the app:
  `token`, `vms`, `host`, `session`, `refresh()`, `set_status()`, `clear()`,
  `page(body, note)`, `wait_or_quit()`, `is_tty()`, `resolve()/resolve_many()`,
  `request_redraw()`, and the `rendered`/`redraw` flags for one-shot mode.
- `actions/` stays as-is (per-VM ops, `run(ctx, vm)`); the `<action> <targets>`
  path is the dispatch fallback into the action registry.

## Tasks  -  COMPLETE

- [x] 1. `commands/base.py` - `CommandContext`, `CONTINUE`/`EXIT`.
- [x] 2. `commands/__init__.py` - registry (discover/get/load/load_errors).
- [x] 3. Migrate simple verbs: `quit`, `version`, `help`, `list/status`, `logout`.
- [x] 4. Migrate page verbs: `health`, `show`, `log`.
- [x] 5. Migrate `overview` (the live loop) into its own file.
- [x] 6. Rewrite `dispatch()` to be registry-first (command registry, then
       action registry, then "unknown").
- [x] 7. Derive Tab-completion vocab and `help` from both registries; deleted
       `BUILTINS_HELP` and the old `if/elif` branches + `_show_*`/`_overview`.
- [x] 8. Make `run_once()` registry-driven (uses `rendered`/`redraw` flags).
- [x] 9. Verified on host (all 9 commands); `help` + completion auto-generated.

## Acceptance

Add `commands/foo.py` with `NAME="foo"` and a `run()` -> `foo` is immediately
dispatchable, Tab-completes, and appears in `help`, with zero edits elsewhere.
Same for `actions/foo.py`.
