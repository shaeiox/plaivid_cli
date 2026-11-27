# Human-readable documentation for `__main__.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/__main__.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Module entry point for `python -m pvm_control_engine`; it delegates to `bootstrap.main()` and propagates the returned status through `SystemExit`.

## 2. Functional summary

Module entry point for `python -m pvm_control_engine`; it delegates to `bootstrap.main()` and propagates the returned status through `SystemExit`.

## 3. Inputs and outputs

This module has no top-level callable. Its externally visible inputs and outputs are its imports, package exports, constants, and any import-time effects described below.

## 4. Execution flow

Importing this module imports `main` from `bootstrap`; executing it calls `main()` and raises `SystemExit` with the returned exit code.

## 5. Functions and methods

No top-level functions or class methods are declared in this file.

## 6. Classes and data structures

No classes are declared in this module.

## 7. Decision-making logic

The following branch conditions are present in the implementation; each selects the corresponding source-code path:

- `__name__ == '__main__'`

## 8. Loops and repeated operations

No explicit loops or comprehensions were found.

## 9. Error handling

No local `try`/`except` handler was found. Exceptions from called dependencies propagate unless caught by a caller.

Explicitly raised exception expressions: `SystemExit(main())`.

## 10. Dependencies and interactions

- **Project imports:** `.bootstrap`.
- **Other imports:** none directly declared.

## 11. Real-world scenario

A caller imports this module and uses the declared API or package exports. See the function/method descriptions for the concrete data flow and side effects; no behavior beyond the implementation is assumed.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`__main__.py` is part of `pvm_control_engine`. Module entry point for `python -m pvm_control_engine`; it delegates to `bootstrap.main()` and propagates the returned status through `SystemExit`. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.
