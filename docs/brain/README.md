# Repository brain: two-project PVM Control

The repository contains exactly two installable Python projects: [`pvm_control_engine/`](../../pvm_control_engine/README.md), distribution `pvm-control-engine` / import `pvm_control_engine`; and [`UI/`](../../UI/README.md), distribution `plaivid-ui` / import `plaivid_ui`. The UI connects to the Engine using the local `plaivid.engine.v1` Unix-domain JSON-RPC contract. Root product metadata and the old `plaivid_cli` runtime package have been removed.

## Navigation

| Need | Start here |
|---|---|
| Project layout and canonical ownership | [Repository map](codebase/REPOSITORY_MAP.md), [module index](codebase/MODULE_INDEX.md) |
| Entry points, install and launch | [Entry points](codebase/ENTRYPOINTS.md), each project README |
| Features and owning tests | [Feature map](codebase/FEATURE_TO_FILE_MAP.md) |
| UI↔Engine wire contract | [API contracts](contracts/API_CONTRACTS.md), [UI IPC](../../UI/docs/IPC.md), [Engine architecture](../../pvm_control_engine/docs/ARCHITECTURE.md) |
| Local development and verification | [Testing workflow](workflows/TESTING.md), [Build workflow](workflows/BUILD.md) |
| System boundary | [Engine boundary](architecture/ENGINE_BOUNDARY.md) |

Other architecture, contracts, histories, and OpenSpec records in this brain remain preserved as reference; where they name the former combined package, they are historical, not current ownership or entry-point guidance. Current project metadata, source trees, and RPC registry are authoritative. Verify current maps with `python scripts/validate_brain.py`.
