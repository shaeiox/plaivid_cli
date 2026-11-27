# Release workflow

This repository has two separate distributions and no automated publishing/deployment pipeline. Do not imply that a local wheel build is a release approval.

## Current package identities

| Distribution | Import package | Console command | Metadata |
|---|---|---|---|
| `pvm-control-engine` | `pvm_control_engine` | `pvm-control-engine` | `pvm_control_engine/pyproject.toml` |
| `plaivid-ui` | `plaivid_ui` | `plaivid` | `UI/pyproject.toml` |

Both currently declare Python `>=3.12`. Engine and UI are built/tested separately; see [`BUILD.md`](BUILD.md), [`TESTING.md`](TESTING.md), and project READMEs. Do not publish a third root product or package Engine internals into the UI wheel.

## Release facts and gates

- Both projects use setuptools/wheel and have independent metadata, entry points, source packages, tests and READMEs.
- Engine wheel must not include `plaivid_ui`; UI wheel must not include `pvm_control_engine`.
- No CI/CD, tags, changelog, automated version bump, lockfile, artifact signing, SBOM, package publishing credentials, deployment automation, or rollback tooling is currently defined.
- The available sandbox has Python 3.11.2; builds and tests there are supplemental only. Supported Python >=3.12 install/runtime validation remains outstanding.
- Real PVM behavior, sbell response semantics, target permissions and the accepted credential-in-argv risk require explicit owner review. The UI has no password/token RPC; login is Engine-local.
- Do not perform real host operations as part of release checks. Follow `pvm_control_engine/docs/REAL_PVM_VALIDATION.md` only under an authorized owner-run procedure.

A release owner must approve versions, platform support, compatibility, security risk, validation evidence, and distribution channel. This document does not invent those policies.
