# Plaivid PVM Control projects

This repository contains two independently installable Python projects:

- [`pvm_control_engine/`](pvm_control_engine/README.md): the standalone Engine, authentication/session owner, approved local `sbell` integration, and Unix-domain JSON-RPC server.
- [`UI/`](UI/README.md): the Textual user interface and its Engine IPC client/DTOs.

They build and install separately. The UI does not ship or import Engine internals; it communicates with the Engine over the versioned local socket contract. There is no third `plaivid_cli` product or root application package.

Repository-wide guidance, historical specifications, and validation tooling remain at the root (`AGENTS.md`, `docs/brain/`, `openspec/`, `.agents/`, and `scripts/`). See each project README for independent development and test commands.
