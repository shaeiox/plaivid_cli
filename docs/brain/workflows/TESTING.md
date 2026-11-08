# Testing

Navigation: [`../README.md`](../README.md) · [`DEVELOPMENT.md`](DEVELOPMENT.md) ·
[`BUILD.md`](BUILD.md) · [`../codebase/FEATURE_TO_FILE_MAP.md`](../codebase/FEATURE_TO_FILE_MAP.md).

## Framework and configuration

- **pytest** with `[tool.pytest.ini_options]` in `pyproject.toml`: `testpaths = ["tests"]`,
  `addopts = "-ra --strict-markers"`. No `pytest.ini`, `tox.ini`, or `conftest.py` exists.
- Dev dependency `pytest>=8.0`, `pytest-cov>=5.0`.
- Coverage config: `[tool.coverage.run] source = ["plaivid_cli"]`, omitting
  `plaivid_cli/legacy/*` and `plaivid_cli/legacy/**/*`.
- Ruff excludes `tests/smoke.py` and `plaivid_cli/legacy/`; Pyright includes only
  `plaivid_cli/` and excludes legacy and tests.

## Test structure

| Path | Type | Content |
|---|---|---|
| `tests/unit/` (32 modules) | Unit + fake-backed integration + Textual Pilot | All automated tests; no host/network access. |
| `tests/fixtures/` | Synthetic data | XML/text fixtures; `tests/fixtures/README.md` explicitly states they are not captured PVM output. |
| `tests/smoke.py` | Opt-in real-host script | Imports `plaivid_cli/legacy/`; not collected by pytest (filename does not match `test_*.py`) and excluded from local verification. Requires `PLAIVID_PASS`. |

There is **no separate integration or system test directory** under `tests/`.
Integration-style behavior is covered inside `tests/unit/` with fakes and Textual Pilot.

## Commands

```bash
python -m pytest -q --ignore=tests/smoke.py          # standard local suite (README.md)
python -m pytest tests/unit -q                       # unit-only equivalent
python -m pytest -q --ignore=tests/smoke.py --cov=plaivid_cli --cov-report=term-missing --cov-report=xml:coverage.xml
ruff check plaivid_cli tests/unit
pyright
python scripts/validate_brain.py                     # documentation drift audit
```

`--ignore=tests/smoke.py` is defensive: it is never collected by default, and the historical
audit confirms it was intentionally never run. Do not run it without owner approval and a
non-production host.

**Coverage expectation:** no threshold is enforced in `pyproject.toml` (no `fail_under`).
`docs/architecture/FINAL_IMPLEMENTATION_AUDIT.md` records a historical 77% active-package
coverage figure from an earlier, smaller suite; treat it as history, not a current gate.
Legacy code is intentionally omitted from coverage.

## Fixtures, fakes, and mocks

| Mechanism | Location | Purpose |
|---|---|---|
| `FakeProvider`, `FakeAudit`, and `runtime(tmp_path)` | `tests/unit/test_cli_and_tui.py::runtime` | Shared composition root for CLI/TUI tests with a fake `PvmGateway`, temporary paths, and fake coordinators. Six other test modules import `runtime`. |
| Synthetic XML/text | `tests/fixtures/objects.xml`, `tests/fixtures/sball-show.xml`, `tests/fixtures/monitoring-metrics.xml`, `tests/fixtures/nic-list.xml`, `tests/fixtures/running-vms.txt`, `tests/fixtures/running-vms-six.txt` | Deterministic parser and monitoring inputs. |
| Fake child processes | `tests/unit/test_process_runner.py`, `tests/unit/test_sbell_client.py`, `tests/unit/test_pvm_adapter.py` | Avoid real `sbell`/`sudo` execution; verify argv, truncation, timeout, and process-group cleanup. |
| Temporary SQLite | `tests/unit/test_audit_adapter.py` | Read-only audit adapter against a disposable DB. |
| Textual Pilot (`run_test`) | `tests/unit/test_cli_and_tui.py`, `tests/unit/test_tui_theme.py`, `tests/unit/test_overview_monitoring.py`, `tests/unit/test_virtual_desktops.py`, `tests/unit/test_multi_select.py`, `tests/unit/test_dashboard_chart_refactor.py` | Mount the real `PlaividTui` / widget trees without a TTY. |
| `monkeypatch`, `capsys` | multiple tests | Env/config isolation, CLI output capture. |

**Timing robustness:** `tests/unit/test_overview_monitoring.py` waits up to 10 ×
`await pilot.pause(.05)` for `tui._refresh_busy` to clear before its final assertion, because
collection runs in a Textual thread worker. Keep that pattern when asserting after async
refresh.

## Important regression suites

| Concern | Tests |
|---|---|
| Layer/import boundaries, unique `CheckableTable`, sibling-page ban | `tests/unit/test_architecture_boundaries.py` |
| Wheel package selection and legacy exclusion | `tests/unit/test_distribution.py` |
| Operation admission, aggregate precedence, exit codes | `tests/unit/test_application_operations.py`, `tests/unit/test_operation_policy.py`, `tests/unit/test_cli_and_tui.py` |
| Collection coalescing, last-good, generation barriers | `tests/unit/test_collection_coordinator.py` |
| Session cache safety / credential gate | `tests/unit/test_session_lifecycle.py` |
| Redaction of human and JSON output | `tests/unit/test_redaction.py`, `tests/unit/test_cli_and_tui.py` |
| Parser correctness with synthetic XML | `tests/unit/test_pvm_parsers.py`, `tests/unit/test_monitoring_metrics_parser.py`, `tests/unit/test_nic_list_parser.py`, `tests/unit/test_pvm_uptime.py` |
| Chart geometry, strict scaling, wall-clock window, palette kwargs | `tests/unit/test_charts.py`, `tests/unit/test_graph_history.py`, `tests/unit/test_background_graphs.py`, `tests/unit/test_dashboard_chart_refactor.py` |
| Overview dashboard, panels, status labels | `tests/unit/test_overview_monitoring.py`, `tests/unit/test_host_metrics_panels.py`, `tests/unit/test_quorum_status.py` |
| VM/Desktop selection, search, multi-select, actions | `tests/unit/test_multi_select.py`, `tests/unit/test_virtual_desktops.py` |
| Theme/palette and responsive layout | `tests/unit/test_tui_theme.py`, `tests/unit/test_group_palette.py` |
| Config/bootstrap/setup script | `tests/unit/test_config.py`, `tests/unit/test_bootstrap.py`, `tests/unit/test_setup_script.py` |
| Process runner / bounded child lifecycle | `tests/unit/test_process_runner.py` |

## Feature → test lookup

`../codebase/FEATURE_TO_FILE_MAP.md` lists the **Tests:** line per feature; use that as the
primary lookup. When changing a feature, run its listed tests plus:

- `tests/unit/test_architecture_boundaries.py` for any import change;
- `tests/unit/test_distribution.py` for any new package/module;
- `tests/unit/test_cli_and_tui.py` for any CLI/TUI entry-point change;
- `python scripts/validate_brain.py` for any documentation/architecture change.

## Validation boundary

All automated tests use fakes and synthetic fixtures. They do **not** verify PVM response
semantics, host permissions, Sball behavior, vendor support, or Python 3.12 platform
compatibility. Owner-run checks are listed in `docs/REAL_PVM_VALIDATION.md`; no test in this
repository contacts a real PVM host.
