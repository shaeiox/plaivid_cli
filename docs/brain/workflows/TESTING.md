# Testing workflow

The two projects have separate test suites and are run from their own directories. Use the installed project development extras and the declared Python 3.12-or-newer runtime. If the local sandbox only has Python 3.11, tests/builds can still provide supplemental checks but do not satisfy the supported-runtime install gate.

```bash
cd pvm_control_engine
python -m pytest -q
ruff check src/pvm_control_engine tests
pyright

cd ../UI
python -m pytest -q
ruff check tui/src/plaivid_ui tests
pyright

cd ..
python scripts/validate_brain.py
```

Engine tests use fake providers, process runners, synthetic XML, and temporary Unix sockets/state. UI tests use fake RPC responses, AST boundary checks and setup-script fakes. Active suites must not issue destructive requests to a real PVM host. The historical combined UI tests are retained under `UI/docs/migration/legacy-tests/` but are intentionally not collected because they instantiate the retired internal runtime. No real-host action or protocol conformance is established by local tests; see `pvm_control_engine/docs/REAL_PVM_VALIDATION.md`.
