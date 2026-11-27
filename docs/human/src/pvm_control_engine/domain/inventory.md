# Human-readable documentation for `inventory.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/domain/inventory.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Pure correlation of independent PVM object and process evidence.

## 2. Functional summary

Pure correlation of independent PVM object and process evidence.

## 3. Inputs and outputs

Public call inputs are the parameters shown in the function and method signatures below. Defaults and annotations are preserved from source. Explicit return expressions are listed with each callable; exceptions and mutations are summarized in the behavior notes.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `merge_inventory(objects: tuple[ObjectVM, ...], process_rows: tuple[ProcessObservation, ...], *, process_available: bool, process_complete: bool | None=None, quality_issues: tuple[str, ...]=()) -> InventoryData`

Join by UUID without changing either source's facts or inventing VMs.

## 6. Classes and data structures

No classes are declared in this module.

## 7. Decision-making logic

The following branch conditions are present in the implementation; each selects the corresponding source-code path:

- `process_complete is None`
- `duplicate_objects`
- `duplicate_process`
- `process_available`
- `obj.state in {'stopped', 'off'} and process is not None` (with an `else` branch)
- `process_complete and obj.state in {'started', 'running', 'paused'} and (process is None)`

## 8. Loops and repeated operations

Iteration is performed by the following loops/comprehensions:

- `item in objects`
- `item in process_rows`
- `(uuid, obj) in usable_objects.items()`
- `(uuid, rows) in object_groups.items() (comprehension)`
- `(uuid, rows) in process_groups.items() (comprehension)`
- `(uuid, rows) in object_groups.items() (comprehension)`
- `(uuid, rows) in process_groups.items() (comprehension)`
- `(uuid, row) in usable_process.items() (comprehension)`

## 9. Error handling

No local `try`/`except` handler was found. Exceptions from called dependencies propagate unless caught by a caller.

No explicit `raise` statement was found in this module.

## 10. Dependencies and interactions

- **Project imports:** `pvm_control_engine.domain.models`.
- **Standard-library/third-party imports:** `__future__`, `collections`.

Related module documentation:

- [`pvm_control_engine.domain.models`](models/__init__.md)

## 11. Real-world scenario

Pure correlation of independent PVM object and process evidence.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`inventory.py` is part of `pvm_control_engine`. Pure correlation of independent PVM object and process evidence. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.
