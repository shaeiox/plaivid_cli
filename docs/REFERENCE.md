# Plaivid command reference

All commands run locally. One-shot reads exit after the requested collection; help/version do not launch PVM tools. Real-host behavior remains **PENDING MANUAL PVM VALIDATION**.

## Reads

```bash
plaivid inventory [--json]
plaivid host|status|overview [--json]
plaivid detail <canonical-uuid> [--json]
plaivid audit [--limit 1..500] [--json]
plaivid config|diagnostics [--json]  Show validated redacted local settings; no PVM calls
```

Inventory prints object-store state and process-observed evidence separately. Host output preserves `sball_state` literally. Audit is optional and read-only. JSON output preserves status, generation, source, freshness metadata, quality issues, and data rather than replacing missing values with healthy defaults.

## Lifecycle

```bash
plaivid start <target> [--json]
plaivid resume <target> [--json]
plaivid stop <target> --approve 'STOP <canonical-uuid>'
plaivid reset <target> --approve 'RESET <canonical-uuid>'
plaivid pause <target> --approve 'PAUSE <canonical-uuid>'
plaivid kill <target> --approve 'KILL <canonical-uuid>'
```

Supported target selectors:

- Canonical UUID
- Exact VM name or unique case-insensitive name prefix
- One-based inventory index
- `all`
- `state:<state>` (object-store state, with `state:running` matching `started` or `running`)
- `process:present` or `process:missing`

Comma-separated selectors form an explicit set. Duplicate targets, ambiguous prefixes, unsupported groups, and empty sets are rejected before dispatch. Bulk operations require a complete current inventory, `PLAIVID_MAX_INVENTORY_AGE_SECONDS`, and approval naming every canonical UUID in resolved order.

For one-target Start/Resume, the explicit command/selection is the intent. Stop, Reset, Pause, and Kill require exact action/UUID approval; Kill is marked critical. The TUI dispatches from the Bulk action dropdown without a confirmation dialog.

## Result and exit meanings

- `SUCCEEDED`: PVM replied `<status>success</status>` (documented envelope, `docs/SBELL-SABAD.md` §3).
- `FAILED`: PVM replied `<status>failed</status>`; the message carries the `errno` and PVM `what` text.
- `OUTCOME_UNKNOWN`: transport error, timeout, or unrecognised status after dispatch. Do not retry blindly; reconcile first.
- `COMMAND_ACCEPTED_UNCONFIRMED`: representable only for a future evidence-backed acceptance mapping; current code does not infer it from `status=success` or process exit status.
- `NOT_STARTED`: bulk target skipped after a prior definite failure, rejection, or unknown result.
- Exit codes: `0` successful read or operation; `1` failure; `2` rejected; `3` partial; `4` outcome unknown.

The implementation intentionally does not claim a command response means the VM has reached its terminal state. Owner verification remains **PENDING MANUAL PVM VALIDATION**.

## TUI

```bash
plaivid
# or
plaivid tui
```

The Textual app requires an interactive TTY. Tabs: Fleet (VM list with a Bulk action dropdown and "Apply to all VMs" toggle, plus the selected-VM details), Host (Sball status and host metrics), and Audit (read-only local audit). `R` refreshes, `Enter` requests details for the selected row, and `Q` exits. The UUID selection is preserved across inventory refreshes.

## Sensitive configuration

`PLAIVID_ALLOW_CREDENTIAL_ARGV=1` explicitly accepts the unresolved risk that `sbell` receives credentials/tokens in process arguments. It is disabled by default and is not a security fix. Review README security notes before enabling.
