# Repository map

```text
.
├── UI/                                  plaivid-ui project root
│   ├── pyproject.toml                   plaivid-ui distribution metadata
│   ├── tui/src/plaivid_ui/              UI package, TUI, socket client, wire DTOs
│   ├── tests/                           active UI tests (fake IPC, boundary, packaging)
│   ├── docs/                            UI architecture and IPC contract
│   └── scripts/                         UI-specific setup tooling
├── pvm_control_engine/                  pvm-control-engine project root
│   ├── pyproject.toml                   Engine distribution metadata
│   ├── src/pvm_control_engine/          Engine package; `bootstrap.py` CLI policy, `composition.py` runtime wiring
│   ├── tests/                           Engine unit and IPC contract tests
│   └── docs/                            Engine README and architecture/host validation
├── docs/brain/                          repository-wide maps/contracts/workflows
├── openspec/                            preserved specifications and change records
├── .agents/                             portable engineering skills
├── scripts/validate_brain.py            repository-wide project/boundary validator
├── AGENTS.md                            contributor/agent entry instructions
└── README.md                            two-project repository overview
```

There is no root installable package, root `pyproject.toml`, `setup.py`, `plaivid_cli` runtime directory, or third application distribution. Build products and virtual environments are ignored artifacts, not source projects.
