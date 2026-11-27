# Documentation audit

**Purpose:** track documentation/implementation drift during the two-project split. Start at [`../README.md`](../README.md) and use [`../workflows/TESTING.md`](../workflows/TESTING.md) for current checks.

## Current validator

`scripts/validate_brain.py` is read-only and standard-library-only. Run it from the repository root:

```sh
python scripts/validate_brain.py
```

It checks required two-project/navigation files, local links in current project maps/contracts, project names and console entry points, package roots, absence of the retired root product, and AST import boundaries across UI modules. It does not prove runtime correctness, schema conformance, every historical reference, or project-wide Markdown link validity.

## Verification record — 2026-11-27

- `python scripts/validate_brain.py`: PASS; 22 required navigation/project files, 38 checked local links, 84 UI modules boundary-checked.
- Engine suite: 85 passed under the available Python 3.11.2 interpreter (supplemental versus declared floor); Ruff clean; Pyright 0 errors with project target 3.12.
- UI suite: 22 passed under Python 3.11.2 (supplemental), including offline Textual mount, retained pure palette/quorum display tests, and setup-project checks; Ruff clean.
- UI full-package Pyright: failed with 308 diagnostics. Most diagnostics stem from Textual mixin composition (members defined on the composed `PlaividTui` are not visible to standalone mixin classes); additional diagnostics include chart/render typing and optional/type narrowing issues. Targeted Pyright on `tui/src/plaivid_ui/engine_client` passes with 0 diagnostics. Full UI type-check remains a follow-up, not a clean result.
- Both project sdists and wheels built in isolated build environments. Wheel contents and entry points were inspected. The only sandbox interpreter is Python 3.11.2 while both distributions retain the accepted `>=3.12` floor; supported-runtime installation remains unverified. Both wheels imported and exposed their parsers under Python 3.11 only with `pip --ignore-requires-python`; this is supplemental packaging smoke, not supported-runtime validation.
- UI-owned socket client ↔ real Engine Unix RPC server smoke test passed for `engine.health` and rejection of an unknown method. The test used a temporary socket and no PVM requests.

## Historical material

Pre-split codebase architecture records, REFACTOR/TASKS notes, product references, and combined UI tests were moved under their owning project in `UI/docs/history/`, `UI/docs/migration/legacy-tests/`, and `pvm_control_engine/docs/`. They remain preserved context; old references to the combined `plaivid_cli` runtime, old UI tabs, or one-package installation are historical and must not override current project READMEs, metadata, `docs/brain/codebase/`, `UI/docs/IPC.md`, or Engine RPC source.

## Remaining external validation

No destructive host action was run. Local tests do not establish sbell/PVM response acceptance, credential visibility on target hosts, real socket permissions under deployment accounts, or action completion semantics. Follow `pvm_control_engine/docs/REAL_PVM_VALIDATION.md` only as an operator-run validation plan. The credential-in-argv behavior remains default-deny and requires the explicit existing acknowledgement.
