# Human-readable documentation for `planner.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/infrastructure/sbell/commands/vm/planner.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Freshness and completeness admission for VM and Desktop operation plans.

## 2. Functional summary

Freshness and completeness admission for VM and Desktop operation plans.

## 3. Inputs and outputs

This module exposes the declared classes and their constructors. Constructor arguments are shown in the method inventory; data fields and defaults are listed in the class section.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `OperationPlanner.__init__(self, collection: CollectionCoordinator, settings: Callable[[], Settings]) -> None`

Reads or updates `self._collection`, `self._settings`. No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `OperationPlanner.create_plan(self, action: Action, targets: tuple[VMRecord, ...], inventory: SectionSnapshot[object], *, is_bulk: bool) -> OperationPlan`

Build an immutable, freshness-checked plan without dispatching.

### `OperationPlanner._build_plan(self, action: Action, targets: tuple[VMRecord, ...], inventory: SectionSnapshot[object], *, is_bulk: bool) -> OperationPlan`

Calls `self._settings`, `tuple`, `self._collection.snapshot.section`, `any`, `OperationPlan`. Reads or updates `settings`, `target_ids`, `current`, `current_records`, `object_section`, `max_age`. Explicit return value(s): `OperationPlan(action=action, target_uuids=target_ids, inventory_generation=inventory.generation, inv`. Can raise `AppError(ErrorKind.POLICY, 'operation targets must be non-empty and unique')`, `AppError(ErrorKind.POLICY, 'multiple targets must be declared as one bulk plan')`, `AppError(ErrorKind.POLICY, 'inventory changed after target selection; refresh and retry')`, `AppError(ErrorKind.POLICY, 'operation plan has no current inventory records')`.

### `OperationPlanner.create_desktop_plan(self, action: Action, targets: tuple[VirtualDesktop, ...], section: SectionSnapshot[object], *, is_bulk: bool) -> OperationPlan`

Admit an exact Desktop target set, including checked bulk subsets.

## 6. Classes and data structures

### `OperationPlanner`

- **Bases:** no explicit base class.
- **Description:** Build immutable plans against current source truth without dispatching.
- **Methods:** `__init__`, `create_plan`, `_build_plan`, `create_desktop_plan`.

## 7. Decision-making logic

The following branch conditions are present in the implementation; each selects the corresponding source-code path:

- `not target_ids or len(set(target_ids)) != len(target_ids)`
- `len(target_ids) > 1 and (not is_bulk)`
- `current is None or current.generation != inventory.generation`
- `not isinstance(inventory.value, InventoryData)`
- `any((current_records.get(record.uuid) != record for record in targets))`
- `object_section is None or object_section.generation != inventory.generation or object_section.status is not CollectionStatus.CURRENT or (object_section.value is None) or (object_section.succeeded_at is None)`
- `max_age is None`
- `not self._collection.is_fresh('objects', max_age_seconds=max_age)`
- `is_bulk and (inventory.status is not CollectionStatus.CURRENT or not self._collection.is_fresh('inventory', max_age_seconds=max_age))`
- `any((record.state_disagreed or record.quality_issues for record in targets))`
- `is_bulk`
- `not ids or len(set(ids)) != len(ids) or (len(ids) > 1 and (not is_bulk))`
- `latest is None or latest != section or section.status is not CollectionStatus.CURRENT or (not isinstance(section.value, tuple))`
- `len(current) != len(section.value) or any((current.get(item.uuid) != item for item in targets))`
- `age is None`
- `not self._collection.is_fresh('desktops', max_age_seconds=age)`
- `section.succeeded_at is None or section.quality_issues`
- `is_bulk`
- `not bulk_may_dispatch(action=action, is_bulk=True, complete=complete, fresh=True, max_age_seconds=settings.max_inventory_age_seconds)`
- `is_bulk`

## 8. Loops and repeated operations

Iteration is performed by the following loops/comprehensions:

- `record in inventory.value.records (comprehension)`
- `item in section.value (comprehension)`
- `record in targets (comprehension)`
- `record in targets (comprehension)`
- `record in targets (comprehension)`
- `item in targets (comprehension)`
- `item in targets (comprehension)`
- `record in targets (comprehension)`

## 9. Error handling

No local `try`/`except` handler was found. Exceptions from called dependencies propagate unless caught by a caller.

Explicitly raised exception expressions: `AppError(ErrorKind.POLICY, 'operation targets must be non-empty and unique')`, `AppError(ErrorKind.POLICY, 'multiple targets must be declared as one bulk plan')`, `AppError(ErrorKind.POLICY, 'inventory changed after target selection; refresh and retry')`, `AppError(ErrorKind.POLICY, 'operation plan has no current inventory records')`, `AppError(ErrorKind.POLICY, 'operation targets do not exactly match current inventory records')`, `AppError(ErrorKind.POLICY, 'mutations require a current successful object inventory')`, `AppError(ErrorKind.POLICY, 'object inventory is too old for a mutation; refresh and retry')`, `AppError(ErrorKind.POLICY, 'bulk mutations require a complete current inventory')`, `AppError(ErrorKind.POLICY, 'a selected VM has conflicting or incomplete state evidence')`, `AppError(ErrorKind.POLICY, 'Desktop targets must be non-empty, unique and explicitly scoped')`, `AppError(ErrorKind.POLICY, 'complete current Desktop inventory required')`, `AppError(ErrorKind.POLICY, 'Desktop targets do not match the current listing')`.

## 10. Dependencies and interactions

- **Project imports:** `pvm_control_engine.application.collection`, `pvm_control_engine.config`, `pvm_control_engine.domain.desktops`, `pvm_control_engine.domain.errors`, `pvm_control_engine.domain.models`, `pvm_control_engine.domain.policies`.
- **Standard-library/third-party imports:** `__future__`, `collections.abc`, `datetime`.

Related module documentation:

- [`pvm_control_engine.application.collection`](../../../../application/collection/__init__.md)
- [`pvm_control_engine.config`](../../../../config.md)
- [`pvm_control_engine.domain.desktops`](../../../../domain/desktops.md)
- [`pvm_control_engine.domain.errors`](../../../../domain/errors.md)
- [`pvm_control_engine.domain.models`](../../../../domain/models/__init__.md)
- [`pvm_control_engine.domain.policies`](../../../../domain/policies.md)

## 11. Real-world scenario

Freshness and completeness admission for VM and Desktop operation plans.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`planner.py` is part of `pvm_control_engine`. Freshness and completeness admission for VM and Desktop operation plans. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.
