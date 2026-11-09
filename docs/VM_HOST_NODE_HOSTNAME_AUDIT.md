# VM `Host` display: node → server hostname mapping audit

**Status:** implemented — see §9 for the delivered delta
**Question:** can the VM detail pane show `node-a (spongebob)` instead of `node-a`, and where would
the hostname come from?
**Baseline:** `arena/86ec82cd-plaivid-cli`, commit `a854ab5`.

Evidence labels: **source-verified** (code path read in this repo) · **doc-only** (repository
documentation) · **fixture-only** (synthetic fixture; `tests/fixtures/README.md` states these are not
captured PVM output) · **unverified** (needs a real host capture).

---

## 1. Verdict

| Question | Answer |
| --- | --- |
| Is there an existing node-ID → server-hostname map anywhere? | **No.** Nothing in the codebase, models or fixtures maps a cluster node to an OS hostname. |
| Is a hostname available at all? | **Yes, but only for the machine that answers the local `sbell` call** — i.e. this node. `monitoring/metrics` → `system_info/host_name` is already parsed into `HostMetrics.hostname` and shown on the Overview System card. |
| Are remote node hostnames available? | **No.** There is no cluster-node inventory read, no remote transport, and `sball master` (the only catalogue entry that might list nodes) has no documented shape, parser, fixture or test. |
| Can `node (`*hostname*`)` be shown safely today? | **Yes, for VMs proven local**: node matches this node's name/ID, or the VM is observed by the local `pvm-running-vms`. Remote VMs must keep showing the identifier alone. |
| Does anything need inventing? | No. The rule is: append a hostname only when the value is known to belong to that node; otherwise show the raw node value. |

---

## 2. Where node identity and hostname live today

| Source (module/command) | Fields | Hostname? | Scope | Parsed today? | Evidence |
| --- | --- | --- | --- | --- | --- |
| `user/objects` VM object | `virtual_machine/cluster/host` | No — node name or number (`node-a` in the fixture; docs call it “node id”) | per VM | **Yes** → `ObjectVM.host` (`parsers/inventory.py:55`) | **doc-only** (`SBELL-SABAD.md:237`) + **fixture-only** |
| `sball/show` | `cluster/node/id`, `name`, `ip`, `sball-state`, `node-state` | **No** — `name` is the PVM node name, `id` a number | local node only | Partly: `name`/`ip`/states in `HostStatus`; **`id` is not parsed** (`parsers/host.py:29-62`) | **doc-only** (`SBELL-SABAD.md:258-271`) + **fixture-only** (`<id>1</id>`, `<name>node-a</name>`) |
| `monitoring/metrics` | `metrics/system_info/{host_name, host_id, platform, kernel}` | **Yes** — `host_name` (fixture: `spongebob`) | local node only | **Yes** → `HostMetrics.hostname` / `.host_id` (`parsers/host.py:117,219`) | **doc-only** + **fixture-only** |
| `monitoring/system` | “host identity (hostname, OS, platform, kernel)” | Yes (documented) | local node only | **No** — never called; the app uses `monitoring/metrics`, whose response carries `system_info` | **doc-only** (`SBELL-SABAD.md:271`) |
| `user/objects` dashboard (`/plaivid/overview/pvm_overview_dashboard`) | `host_list/host_dashboard/{name,id}` | Possibly — mapped to `DashboardSample.host_name` / `.host_id` | local node (presumed) | Yes, but the **schema is unverified**; `MONITORING_DASHBOARD.md:24,26` makes its capture an open acceptance item, and `openspec/changes/redesign-monitoring-tui/design.md:9` calls it proposed | **unverified** |
| `pvm-running-vms` | 8 columns: ROW PID UPTIME PORT VCPU MEMORY UUID NAME | **No** host/node column | local processes only | Yes (process evidence) | **doc-only** + **fixture-only** |
| `local /proc` (`LocalHostSample`) | `socket.gethostname()`, CPU/mem/load | Yes (OS hostname of the machine running Plaivid) | client host | Yes (`local_monitor.py:91`) | **source-verified** |
| `sball/master` | unknown | unknown | cluster-wide? | **No** — no parser, no fixture, no call site | **doc-only** catalogue entry (`Plaivid CLI & sbell Reference.md:90`) |

`monitoring/metrics` is therefore the authoritative hostname source today; `sball/show` supplies the
node name/number but no hostname; the dashboard object is not evidence yet.

### 2.1 Why a cluster-wide map does not exist

* The client is a **local** command runner: “These are local commands, not SSH endpoints. No
  hostname, remote-agent … setting is supported” (`docs/ENVIRONMENT.md:38`).
* Every host identity field describes **the node that answered**: `sball/show` returns one
  `<cluster><node>`; `monitoring/metrics` returns one `system_info`.
* No module enumerates cluster nodes. There is no `cluster` module; the only candidate is
  `sball master`, which appears solely in the command catalogue and has no response shape in this
  repository.

So a remote VM (`cluster/host` naming another node) can never gain a hostname from the current
read set. Any attempt would be a guess and must be rejected.

---

## 3. Current `Host` field inspection

| Layer | Current behaviour |
| --- | --- |
| Parser | `host = machine.findtext("cluster/host")` — verbatim, no mapping (`parsers/inventory.py:55`) |
| Model | `ObjectVM.host` (optional string; whitespace → `None`, `domain/models/inventory.py:24,30`), `VMRecord.host` property (`:86-87`) |
| Renderer | `host = record.host or (detail.host if detail is not None else None)` → `_value(host)` emits the raw string or `—` (`components/details.py:114`) |
| Value shape | A PVM node identifier: a name (`node-a` in the fixture) or a number (`1` per the docs’ “node id” and the user’s observation). It is **not** a hostname |
| Hostnames elsewhere | `HostMetrics.hostname` is rendered on Overview (System information card) but is **not** attached to any VM record; `HostSample`/`DashboardSample.host_name` are equally unconnected |

Notable gaps that block a naive join:

1. `HostStatus` exposes **no** hostname and **no** node id; `HostMetrics.host_id` is a host UUID
   (`00000000-0000-5355-…`), not a node number.
2. `HostStatus` and `HostMetrics` describe **one** node — the local one. There is no per-node list.
3. `ObjectVM`/`VMRecord` carry no hostname field, and `merge_inventory` is a pure objects ×
   processes join with no host context.

---

## 4. Recommended matching strategy (local identity only)

Build one **local node identity** from data the app already collects:

```
NodeIdentity
  name      <- HostStatus.name            (sball/show  node/name)      e.g. node-a
  node_id   <- HostStatus.node_id         (sball/show  node/id)        e.g. 1        [new field]
  hostname  <- HostMetrics.hostname       (monitoring/metrics)         e.g. spongebob
              or LocalHostSample.hostname (socket.gethostname)         fallback
  source    <- "monitoring/metrics" | "local /proc"   (display attribution only)
```

`HostStatus.node_id` does not exist yet; parsing `<id>` (with `resource_usage/node_id` as a
cross-check) is a one-field parser addition verified against `sball-fixture` — worth doing because
the reporter sees numeric node values as well as names.

Matching and display rules (pure function, no I/O):

| Case | Rendered `Host` |
| --- | --- |
| `host` matches identity by name **or** id, hostname known | `node-a (spongebob)` / `1 (spongebob)` — raw node value kept, hostname appended |
| `host` matches, hostname unknown | `node-a` (current behaviour) |
| `host` empty and `record.process_seen` (proven local) | `this node (spongebob)` *(optional; today this case renders `—`)* |
| `host` names another node (no match) | raw value only — **never** append the local hostname |
| `host` names another node **but** `process_seen` | raw value only, and ideally a consistency warning: local process evidence contradicts the object’s node |
| `host == hostname` (case-insensitive) | one value, no parentheses |
| `host` is `auto` (start placeholder) | `auto`, never decorated |
| nothing known | `—` |

Formatting details:

* Parentheses and a single space: `f"{node} ({hostname})"`; ellipsis/folding is the renderer’s job.
* `Host` shares the pane’s flexible fourth column, so a long `node (hostname)` folds rather than
  clipping. At 80 columns `node-1 (spongebob)` (18 chars) fits comfortably; very long FQDN-style
  hostnames will wrap — acceptable, but consider an ellipsis cap (~40 chars) if the product
  prefers one line.
* All values still pass through `_present()`/`redact_text()`; no new secret surface.

---

## 5. Where the hostname would come from at runtime

| Fact | Consequence |
| --- | --- |
`CollectionCoordinator._snapshot_locked` returns **all retained sections**, not only the ones just requested (`coordinator.py:279-284`) | hostname data collected on Overview stays readable on the Fleet tab |
| Login lands on Overview first (`session.py:173-181`), whose schedule collects `host_metrics` + `dashboard` + `inventory` every ≥18 s and `host_status` every 2 s (`application/overview.py:101-121`) | identity is normally present by the time the user opens Virtual Machines |
| While another tab is active, only `local_host` is sampled in the background (`refresh.py:101-106`, `application/overview.py:87-99`) | `LocalHostSample.hostname` is the only **fresh** identity on the Fleet tab; PVM hostname ages but hostnames are stable |
| Fleet refresh requests `inventory` only (`refresh.py:108-120`) | do **not** add `monitoring/metrics` to the 3 s loop; reuse retained sections, fall back to node-only when absent |

Recommended precedence: `HostMetrics.hostname` (PVM-reported) → `LocalHostSample.hostname`
(local OS, free and always fresh) → none. Ignore `DashboardSample.host_name` until its schema is
validated, and never call it a verified host-ID match (`MONITORING_DASHBOARD.md:26`).

Availability is best-effort: if the user reaches the VM page before the first Overview batch, or
both reads fail, the pane keeps the node identifier alone — no `— (hostname)` fragments.

---

## 6. Proposed architecture (next phase, no code yet)

1. **Domain** — `NodeIdentity` (frozen dataclass) and a pure `describe_host(node, identity,
   process_seen)` in `plaivid_cli/domain/` (or `domain/models/host.py`). Unit-testable without
   Textual. `describe_host` implements §4 and returns `None`/raw node/`node (host)`.
2. **Parser/model** — add `HostStatus.node_id` parsed from `cluster/node/id` (fallback
   `resource_usage/node_id`), so numeric `cluster/host` values can be matched locally.
3. **Application/presentation glue** — when a snapshot is published, build and cache the identity
   from `host_status` + `host_metrics`/`local_host` (`value` or `last_good_value`); expose it as an
   app-level attribute (the mixins already share app state).
4. **Renderer** — pass the identity into `build_vm_detail(record, detail, palette, node=…)` and
   render `describe_host(...)` in the existing `Host` cell. `selection.py` forwards the cached
   identity; no new collection section.
5. **Tests** — parser (`sball/show` id), `describe_host` truth table (match by name, match by id,
   mismatch, empty, `auto`, `node == hostname`, no hostname), pane render with/without identity,
   and one Pilot test asserting `node-a (spongebob)` appears from the existing fixtures.
6. **Docs** — update the pane contract in `docs/brain/contracts/DATA_MODELS.md`, `FILE_CATALOG.md`
   and the detail-pane RCA §10 once implemented.

Explicitly **out of scope**: deriving hostnames for remote nodes, `sball master` integration,
dashboard-based identity, and any change to `pvm-running-vms`.

---

## 7. Risks and open questions

| # | Risk / question | Handling |
| --- | --- | --- |
| 1 | `cluster/host` may be a name or a number depending on install (**unverified**) | Match against both `HostStatus.name` and the new `node_id`; always display the raw value unchanged |
| 2 | A remote VM could share a string with the local node (e.g. both `1` after a re-cluster) | Only append when the match is exact against the local identity; treat a `process_seen` contradiction as a warning, not a decoration |
| 3 | Plaivid could run on a different machine from the PVM host | Prefer the PVM-reported `HostMetrics.hostname`; the local OS hostname is a fallback only |
| 4 | Dashboard host identity is unverified and may use a different id space (`id: 42` in tests vs a UUID `host_id` in metrics) | Do not use it for mapping without a captured response |
| 5 | A hostname can be stale (renamed host) | Hostnames are stable per boot/install; showing the last known value is acceptable, and the node value is always shown too |
| 6 | Cluster-wide hostname display (for remote VMs) | Blocked: requires a real `sball master` (or equivalent) capture and a parser; until then remote VMs show the node identifier only |
| 7 | Long hostnames in a narrow pane | `Host` is in the wrapping column; add an ellipsis cap only if one-line rows are required |

**Required captures before any remote mapping work:** a redacted `sball master` response (node list
shape, whether it carries names/IPs/hostnames), and a redacted
`/plaivid/overview/pvm_overview_dashboard` response if the dashboard identity is to be trusted.

---

## 8. Evidence appendix

* `plaivid_cli/infrastructure/pvm/parsers/inventory.py:55` — `cluster/host` → `ObjectVM.host`
* `plaivid_cli/domain/models/inventory.py:24,30,86-87` — `ObjectVM.host`, normalisation, `VMRecord.host`
* `plaivid_cli/presentation/tui/pages/virtual_machines/components/details.py:114` — Host cell value
* `plaivid_cli/infrastructure/pvm/parsers/host.py:29-62` — `sball/show` parse (no `id`); `:117,219` — `host_id`, `hostname`
* `plaivid_cli/domain/models/host.py:11-26` — `HostStatus` fields (no hostname, no node id)
* `plaivid_cli/infrastructure/pvm/adapter/local.py:215-218` — `monitoring/metrics` is the only host-identity read
* `plaivid_cli/infrastructure/pvm/overview.py:17-36` — dashboard `host_list/host_dashboard/{name,id}`
* `plaivid_cli/infrastructure/local_monitor.py:91` — `socket.gethostname()`
* `plaivid_cli/application/collection/coordinator.py:279-284` — snapshots retain all sections
* `plaivid_cli/presentation/tui/refresh.py:101-120`, `plaivid_cli/application/overview.py:87-121` — cadence and section demand
* `plaivid_cli/legacy/monitoring.py:171-172` — historical precedent: node name was used as a hostname fallback (legacy only)
* `tests/fixtures/sball-show.xml` (`<id>1</id>`, `<name>node-a</name>`), `tests/fixtures/monitoring-metrics.xml` (`host_name=spongebob`, `host_id=00000000-0000-5355-…`), `tests/fixtures/objects.xml` (`<host>node-a</host>`)
* `docs/SBELL-SABAD.md:237,258-273`; `docs/Plaivid CLI & sbell Reference.md:90`; `docs/MONITORING_DASHBOARD.md:24,26`; `docs/ENVIRONMENT.md:38`

---

## 9. Implementation outcome

Delivered on `arena/86ec82cd-plaivid-cli` on top of `a854ab5`.

| Area | Change |
| --- | --- |
| Domain | `describe_host(node, local_hostname=None, local_node_id=None, *, local_node_name=None)` in `domain/models/host.py` (exported from `domain.models`); pure, no I/O |
| Parser | `HostStatus.node_id` from `sball/show` `node/id`, falling back to `resource_usage/node_id` |
| Snapshot → UI | `OverviewMixin._remember_local_identity()` caches node name, node id and hostname from `host_status` + `host_metrics` (falling back to `local_host`) on every published snapshot |
| Renderer | `build_vm_detail(..., local_hostname=…, local_node_id=…, local_node_name=…)` → `describe_host()` in the existing `Host` cell |

Deltas from the audit's proposal:

* `describe_host()` takes an extra **keyword-only** `local_node_name`. The approved signature alone
  could not match `node-a`, because `local_hostname` is `spongebob` and `local_node_id` is `1`
  (`sball/show` returns the node name separately). The documented positional signature is
  unchanged; the extra keyword defaults to `None`.
* The hostname is not attached to `VMRecord`; it stays a presentation-time decoration built from
  retained host sections, so the inventory model and `merge_inventory` are untouched.

Rendering rules now in force: local match → `node-a (spongebob)` / `1 (spongebob)`; node equals
hostname → `spongebob`; another node → `node-b`; hostname unknown → `node-a`; `auto` → `auto`;
empty → `—`.

Verification: `pytest tests/unit` → **363 passed** (baseline 358 + 5); `ruff check .` clean;
`scripts/validate_brain.py` passes. Two intermediate full runs hit pre-existing fixed-pause timing
flakes in bulk/desktop action tests (`test_multi_select`, `test_cli_and_tui`,
`test_virtual_desktops`); each passes in isolation and the final full run is green.
