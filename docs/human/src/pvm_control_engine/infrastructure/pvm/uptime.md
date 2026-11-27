# Human-readable documentation for `uptime.py`

## 1. File overview

- **Source path:** `pvm_control_engine/src/pvm_control_engine/infrastructure/pvm/uptime.py`
- **Language:** Python
- **File type:** Python package/module
- **Primary responsibility:** Derive the sballd service uptime from ``systemctl status sballd`` output.

## 2. Functional summary

Derive the sballd service uptime from ``systemctl status sballd`` output.

## 3. Inputs and outputs

Public call inputs are the parameters shown in the function and method signatures below. Defaults and annotations are preserved from source. Explicit return expressions are listed with each callable; exceptions and mutations are summarized in the behavior notes.

## 4. Execution flow

The module is invoked through its declared API rather than running as a standalone program. The main callables and their internal calls/returns are summarized in section 5; imports and cross-module links are listed in section 10.

## 5. Functions and methods

### `sball_started_at(status_text: str) -> datetime | None`

Calls `_SINCE.search`, `datetime.strptime`, `' '.join`, `match.groups`. Reads or updates `match`. Explicit return value(s): `None`, `datetime.strptime(' '.join(match.groups()), '%Y-%m-%d %H:%M:%S %z')`.

### `sball_uptime_seconds(status_text: str, now: datetime) -> float | None`

Seconds since the service became active; None unless it is verifiably running.

## 6. Classes and data structures

No classes are declared in this module.

### Module-level values

- `_SINCE` = `re.compile('^\\s*Active:\\s+active \\(running\\) since \\w{3} (\\d{4}-\\d{2}-\\d{2}) (\\d{2}:\\d{2}:\\d{2}) ([+-]\\d{4});', re.MULTILINE)`

## 7. Decision-making logic

The following branch conditions are present in the implementation; each selects the corresponding source-code path:

- `match is None`
- `started is None or now.tzinfo is None`
- `elapsed >= 0` (with an `else` branch)

## 8. Loops and repeated operations

No explicit loops or comprehensions were found.

## 9. Error handling

The module contains these exception-handling clauses:

- `try` block (line 19) handles: ValueError.

No explicit `raise` statement was found in this module.

## 10. Dependencies and interactions

- **Project imports:** none directly declared.
- **Standard-library/third-party imports:** `__future__`, `re`, `datetime`.

## 11. Real-world scenario

Derive the sballd service uptime from ``systemctl status sballd`` output.

## 12. Technical details and limitations

Behavior is bounded by the source contracts and imported dependencies. Environment-specific integration details (for example, external daemon responses or deployment permissions) require validation in the target environment. The module-level AST scan identifies implementation structure but does not claim runtime outcomes for unexecuted branches.

## 13. Call-flow diagram

```mermaid
flowchart TD
  sball_started_at["sball_started_at"] --> call_0["_SINCE.search"]
  sball_started_at["sball_started_at"] --> call_1["datetime.strptime"]
  sball_started_at["sball_started_at"] --> call_2["' '.join"]
  sball_started_at["sball_started_at"] --> call_3["match.groups"]
  sball_uptime_seconds["sball_uptime_seconds"] --> call_4["sball_started_at"]
  sball_uptime_seconds["sball_uptime_seconds"] --> call_5["(now - started).total_seconds"]
```

## 14. Human-readable summary

`uptime.py` is part of `pvm_control_engine`. Derive the sballd service uptime from ``systemctl status sballd`` output. Its concrete interfaces, data structures, decisions, error paths, and direct dependencies are documented above; identifiers and source filenames are retained verbatim.
