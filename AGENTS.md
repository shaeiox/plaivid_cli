# AGENTS.md — repository entry point

This repository contains exactly two independently installable Python projects for local Plaivid PVM control:

- `pvm_control_engine/`: Engine package `pvm_control_engine`, distribution `pvm-control-engine`.
- `UI/`: UI package `plaivid_ui`, distribution `plaivid-ui`.

They communicate only over the approved local Unix-domain `plaivid.engine.v1` JSON-RPC interface. The UI must not import Engine internals or the retired `plaivid_cli` package and must not perform PVM/session/sbell/process work. The Engine exclusively owns authentication/session, UUID resolution, PVM reads, sbell commands and local process execution. Read `docs/brain/README.md`, `docs/brain/codebase/REPOSITORY_MAP.md`, and `docs/brain/architecture/ENGINE_BOUNDARY.md` before architecture work; project READMEs and `UI/docs/IPC.md` are the next navigation points.

## Mandatory workflow

1. Read this file and `docs/brain/README.md`.
2. Classify the task; consult current project architecture and contract docs.
3. Identify canonical files via `docs/brain/codebase/MODULE_INDEX.md` and `FEATURE_TO_FILE_MAP.md`.
4. Inventory affected source, metadata, tests, imports, docs and entry points.
5. Write an impact analysis before editing: affected files, contracts, tests and docs.
6. Preserve user-visible behavior, safety/auth/freshness/concurrency/bulk/redaction/uncertain-outcome semantics.
7. Keep product files under their owning project; root files are repository governance/tooling only.
8. Use mocks/fakes and do not run destructive real-host actions.
9. Run independent project tests/lint/types/builds as relevant and `python scripts/validate_brain.py`.
10. Update the project maps and contract documentation whenever responsibilities, dependencies or interfaces change.

## Architecture constraints

- Exactly two products; no root app metadata/runtime package or third shared package.
- UI-owned IPC client and wire DTOs remain under `UI/`; Engine transport/dispatch and all local PVM execution remain under `pvm_control_engine/`.
- Engine RPC dispatch is explicit and allowlisted. Never add arbitrary command/module/XML/argv dispatch or a redundant shared runtime wrapper.
- Preserve credential argv default-deny policy, bounded process execution, redaction, no automatic retry on uncertain outcomes, current inventory binding, mutation barriers, bulk limits and approved local-sbell integration.
- No HTTP/HTTPS, nginx/httpd, sabad, or raw sballd protocol.
- Do not rewrite the Engine in another language. Do not switch branches, commit, push or merge unless the user explicitly asks.

The project brain is a navigation aid, not a substitute for source/config/tests. If documentation conflicts with the current implementation, verify the source and record the mismatch in `docs/brain/maintenance/DOCUMENTATION_AUDIT.md`. Run `python scripts/validate_brain.py` after map or contract changes. The `.agents/skills/` directory contains portable repository skills; read an applicable `SKILL.md` when useful.
