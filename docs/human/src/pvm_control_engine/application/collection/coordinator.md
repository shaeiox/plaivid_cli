# Human-readable documentation for `coordinator.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/application/collection/coordinator.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Single owner for local reads, source freshness, and last-good publication.

## 2. Functional summary

Single owner for local reads, source freshness, and last-good publication.

## 3. Inputs and outputs

This module exposes the declared classes and their constructors. Constructor arguments are shown in the method inventory; data fields and defaults are listed in the class section.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `CollectionCoordinator.__init__(self, provider: PvmGateway, *, refresh_interval: float=3.0) -> None`

Calls `cast`, `ThreadPoolExecutor`, `threading.RLock`, `set`, `SectionReader`. Reads or updates `self._provider`, `self._monitor`, `self.refresh_interval`, `self._executor`, `self._lock`, `self._sections`. No explicit return statement; the function returns `None` unless an exception interrupts execution. Can raise `ValueError('refresh_interval must be positive')`.

### `CollectionCoordinator.snapshot(self) -> ApplicationSnapshot`

Calls `self._snapshot_locked`. Explicit return value(s): `self._snapshot_locked()`.

### `CollectionCoordinator.request_refresh(self, token: str, *, sections: Iterable[str]=('inventory', 'host_status', 'host_metrics')) -> Future[ApplicationSnapshot]`

Calls `normalize_sections`, `Future`, `hashlib.sha256(token.encode('utf-8')).hexdigest`, `RuntimeError`, `self._launch_locked`. Reads or updates `requested`, `token_identity`, `outer`, `key`, `self._pending`, `old`. Explicit return value(s): `outer`, `self._active[1]`, `self._pending[3]`. Can raise `RuntimeError('collection coordinator is closed')`.

### `CollectionCoordinator.collect_once(self, token: str, *, sections: Iterable[str]=('inventory', 'host_status', 'host_metrics')) -> ApplicationSnapshot`

Perform one bounded request through the owned read lane.

### `CollectionCoordinator.begin_mutation(self, target_uuids: Iterable[str], *, expected_inventory_generation: int | None=None, expected_desktop_generation: int | None=None, max_age_seconds: float | None=None, require_complete_inventory: bool=False) -> int`

Atomically validate an optional plan generation and erect its barrier.

### `CollectionCoordinator.end_mutation(self, target_uuids: Iterable[str], *, section_name: str='inventory') -> ApplicationSnapshot`

Calls `canonical_uuid`, `ValueError`, `datetime.now`, `time.monotonic`, `self._mutating.difference_update`. Reads or updates `targets`, `(now, monotonic)`, `self._generation`, `prior`, `snapshot`, `self._sections[section_name]`. Explicit return value(s): `snapshot`. Can raise `ValueError('unsupported mutation section')`.

### `CollectionCoordinator.is_fresh(self, section_name: str, *, max_age_seconds: float | None) -> bool`

Calls `self._sections.get`, `section_is_fresh`. Reads or updates `section`. Explicit return value(s): `False`, `section_is_fresh(section, max_age_seconds)`.

### `CollectionCoordinator.clear_desktop_session(self) -> None`

Discard prior operator's Desktop identities and in-flight read publication.

### `CollectionCoordinator.close(self) -> None`

Calls `self._executor.shutdown`, `pending[3].set_exception`, `pending[3].done`, `RuntimeError`. Reads or updates `self._closed`, `pending`, `self._pending`. No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `CollectionCoordinator._get_section(self, name: str) -> SectionSnapshot[object] | None`

Calls `self._sections.get`. Explicit return value(s): `self._sections.get(name)`.

### `CollectionCoordinator._launch_locked(self, key: tuple[object, ...], token: str, requested: tuple[str, ...], outer: Future[ApplicationSnapshot]) -> None`

Calls `self._executor.submit`, `inner.add_done_callback`, `self._finish`. Reads or updates `inner`, `self._generation`, `generation`, `mutation_epoch`, `self._active`. No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `CollectionCoordinator._finish(self, key, outer, inner) -> None`

Calls `inner.cancelled`, `outer.done`, `outer.cancel`, `inner.exception`, `pending[3].set_exception`. Reads or updates `self._active`, `(pending, self._pending)`. No explicit return statement; the function returns `None` unless an exception interrupts execution.

### `CollectionCoordinator._collect(self, token: str, requested: tuple[str, ...], generation: int, mutation_epoch: int) -> ApplicationSnapshot`

Calls `datetime.now`, `time.monotonic`, `self._reader.collect`, `publish_results`. Reads or updates `started_at`, `started_mono`, `results`. Explicit return value(s): `publish_results(self._sections, results, generation=generation, current_epoch=self._mutation_epoch, `.

### `CollectionCoordinator._snapshot_locked(self) -> ApplicationSnapshot`

Calls `ApplicationSnapshot`, `datetime.now`, `tuple`, `sorted`. Explicit return value(s): `ApplicationSnapshot(generation=self._generation, created_at=datetime.now(UTC), sections=tuple((self.`.

## 6. Classes and data structures

### `CollectionSuperseded`

- **Bases:** RuntimeError.
- **Description:** A newer bounded pending refresh replaced this obsolete request.

### `CollectionCoordinator`

- **Bases:** no explicit base class.
- **Description:** Serializes blocking reads and retains independent last-good sections.
- **Methods:** `__init__`, `snapshot`, `request_refresh`, `collect_once`, `begin_mutation`, `end_mutation`, `is_fresh`, `clear_desktop_session`, `close`, `_get_section`, `_launch_locked`, `_finish`, `_collect`, `_snapshot_locked`.

## 7. Decision-making logic

The following branch conditions are present in the implementation; each selects the corresponding source-code path:

- `refresh_interval <= 0`
- `not targets`
- `section_name not in {'inventory', 'desktops'}`
- `max_age_seconds is None or max_age_seconds <= 0`
- `self._closed`
- `self._mutating`
- `self._active is None`
- `self._active[0] == key`
- `self._pending is not None and self._pending[0] == key`
- `self._pending is not None`
- `expected_inventory_generation is not None and expected_desktop_generation is not None`
- `expected_desktop_generation is not None`
- `expected_inventory_generation is not None`
- `self._pending is not None`
- `prior is not None`
- `not self._mutating and self._active is None and (self._pending is not None)`
- `self._pending is not None`
- `pending and (not pending[3].done())`
- `inner.cancelled()` (with an `else` branch)
- `self._active is not None and self._active[0] == key`
- `self._closed` (with an `else` branch)
- `self._pending is not None and self._pending[0] == key`
- `self._pending is not None and (not self._pending[3].done())`
- `not old.done()`
- `desktops is None or desktops.generation != expected_desktop_generation or desktops.status is not CollectionStatus.CURRENT or (not isinstance(desktops.value, tuple)) or (not section_is_fresh(desktops, max_age_seconds)) or (not targets.issubs`
- `inventory is None or inventory.generation != expected_inventory_generation or inventory.status not in {CollectionStatus.CURRENT, CollectionStatus.PARTIAL} or (require_complete_inventory and inventory.status is not CollectionStatus.CURRENT) `
- `not pending.done()`
- `not pending.done()`
- `not outer.done()`
- `inner.exception() is not None` (with an `else` branch)
- `pending is not None and (not pending[3].done())`
- `not self._mutating and self._pending is not None`
- `not outer.done()`
- `not outer.done()`

## 8. Loops and repeated operations

Iteration is performed by the following loops/comprehensions:

- `uuid in target_uuids (comprehension)`
- `uuid in target_uuids (comprehension)`
- `name in sorted(self._sections) (comprehension)`
- `item in desktops.value (comprehension)`

## 9. Error handling

No local `try`/`except` handler was found. Exceptions from called dependencies propagate unless caught by a caller.

Explicitly raised exception expressions: `ValueError('refresh_interval must be positive')`, `ValueError('mutation barrier requires at least one target')`, `ValueError('unsupported mutation section')`, `RuntimeError('collection coordinator is closed')`, `ValueError('only one inventory barrier may be selected')`, `CollectionSuperseded('Desktop inventory changed or expired before dispatch')`, `CollectionSuperseded('inventory changed or expired immediately before dispatch')`.

## 10. Dependencies and interactions

- **Project imports:** `pvm_control_engine.application.collection.freshness`, `pvm_control_engine.application.collection.publisher`, `pvm_control_engine.application.collection.sections`, `pvm_control_engine.application.ports`, `pvm_control_engine.domain.models`.
- **Standard-library/third-party imports:** `__future__`, `hashlib`, `threading`, `time`, `collections.abc`, `concurrent.futures`, `datetime`, `typing`.

Related module documentation:

- [`pvm_control_engine.application.collection.freshness`](freshness.md)
- [`pvm_control_engine.application.collection.publisher`](publisher.md)
- [`pvm_control_engine.application.collection.sections`](sections.md)
- [`pvm_control_engine.application.ports`](../ports.md)
- [`pvm_control_engine.domain.models`](../../domain/models/__init__.md)

## 11. Real-world scenario

Single owner for local reads, source freshness, and last-good publication.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 14. Human-readable summary

`coordinator.py` is part of `pvm_control_engine`. Single owner for local reads, source freshness, and last-good publication. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.
