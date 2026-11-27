# Human-readable documentation for `reader.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/application/collection/reader.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Read provider sections and assemble the inventory read model.

## 2. Functional summary

Read provider sections and assemble the inventory read model.

## 3. Inputs and outputs

This module exposes the declared classes and their constructors. Constructor arguments are shown in the method inventory; data fields and defaults are listed in the class section.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `SectionReader.__init__(self, provider: PvmGateway, get_section) -> None`

Calls `cast`. Reads or updates `self._provider`, `self._monitor`, `self._get_section`. No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `SectionReader.collect(self, token: str, requested: tuple[str, ...]) -> dict[str, SourceResult[object]]`

Calls `self._read`, `results.get`, `section.startswith`, `merge_inventory`, `SourceResult`. Reads or updates `results`, `needs_objects`, `needs_processes`, `results['objects']`, `results['processes']`, `object_result`. Explicit return value(s): `results`.

### `SectionReader._read(self, name: str, call, source: str) -> SourceResult[object]`

Calls `time.monotonic`, `datetime.now`, `call`, `SourceResult`, `isinstance`. Reads or updates `started`, `attempted`, `result`, `message`. Explicit return value(s): `SourceResult(value=result.value, status=result.status, source=result.source or source, error=result.`, `SourceResult(value=None, status=CollectionStatus.UNAVAILABLE, source=source, error=message, attempte`.

## 6. Classes and data structures

### `SectionReader`

- **Bases:** no explicit base class.
- **Description:** Perform provider reads and domain-level source correlation for one request.
- **Methods:** `__init__`, `collect`, `_read`.

## 7. Decision-making logic

The following branch conditions are present in the implementation; each selects the corresponding source-code path:

- `needs_objects`
- `needs_processes`
- `'inventory' in requested`
- `'desktops' in requested`
- `'host_status' in requested`
- `'host_metrics' in requested`
- `'dashboard' in requested`
- `'local_host' in requested`
- `'physical_nics' in requested`
- `'nic_samples' in requested`
- `'tap_mapping' in requested`
- `object_result.value is not None` (with an `else` branch)
- `discovered is None`
- `discovered is not None and isinstance(discovered.value, tuple)` (with an `else` branch)
- `section.startswith('detail:')`
- `prior_nics is not None`
- `object_result.status is CollectionStatus.PARTIAL or process_result.status is not CollectionStatus.CURRENT or bool(merged.quality_issues) or any((record.state_disagreed for record in merged.records))` (with an `else` branch)
- `isinstance(exc, AppError)` (with an `else` branch)
- `process_available` (with an `else` branch)

## 8. Loops and repeated operations

Iteration is performed by the following loops/comprehensions:

- `section in requested`
- `nic in discovered.value (comprehension)`
- `record in merged.records (comprehension)`

## 9. Error handling

The module contains these exception-handling clauses:

- `try` block (line 156) handles: Exception.

No explicit `raise` statement was found in this module.

## 10. Dependencies and interactions

- **Project imports:** `pvm_control_engine.application.ports`, `pvm_control_engine.domain.errors`, `pvm_control_engine.domain.inventory`, `pvm_control_engine.domain.models`, `pvm_control_engine.domain.overview`.
- **Standard-library/third-party imports:** `__future__`, `time`, `datetime`, `typing`.

Related module documentation:

- [`pvm_control_engine.application.ports`](../ports.md)
- [`pvm_control_engine.domain.errors`](../../domain/errors.md)
- [`pvm_control_engine.domain.inventory`](../../domain/inventory.md)
- [`pvm_control_engine.domain.models`](../../domain/models/__init__.md)
- [`pvm_control_engine.domain.overview`](../../domain/overview.md)

## 11. Real-world scenario

Read provider sections and assemble the inventory read model.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`reader.py` is part of `pvm_control_engine`. Read provider sections and assemble the inventory read model. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.
