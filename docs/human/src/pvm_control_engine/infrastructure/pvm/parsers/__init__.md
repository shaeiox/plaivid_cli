# Human-readable documentation for `__init__.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/infrastructure/pvm/parsers/__init__.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Pure PVM response parsers with a stable public import surface.

## 2. Functional summary

Pure PVM response parsers with a stable public import surface.

## 3. Inputs and outputs

This module has no top-level callable. Its externally visible inputs and outputs are its imports, package exports, constants, and any import-time effects described below.

## 4. Execution flow

Python executes the package imports and re-exports in source order. No additional runtime workflow is implied beyond the module-level statements recorded below.

## 5. Functions and methods

No top-level functions or class methods are declared in this file.

## 6. Classes and data structures

No classes are declared in this module.

### Module-level values

- `__all__` = `['parse_metrics', 'parse_object_inventory', 'parse_process_rows', 'parse_sball_status', 'parse_tap_mapping', 'parse_vm_detail', '_parse_vcpu']`

## 7. Decision-making logic

No explicit conditional or pattern-matching branches were found in the module AST.

## 8. Loops and repeated operations

No explicit loops or comprehensions were found.

## 9. Error handling

No local `try`/`except` handler was found. Exceptions from called dependencies propagate unless caught by a caller.

No explicit `raise` statement was found in this module.

## 10. Dependencies and interactions

- **Project imports:** `.common`, `.host`, `.inventory`, `.vm_detail`.
- **Other imports:** none directly declared.

## 11. Real-world scenario

Pure PVM response parsers with a stable public import surface.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`__init__.py` is part of `pvm_control_engine`. Pure PVM response parsers with a stable public import surface. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.
