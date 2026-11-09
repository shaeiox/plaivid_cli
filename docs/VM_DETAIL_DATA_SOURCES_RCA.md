# VM Detail Pane — Data Source Root Cause Analysis

**Status:** implemented — see §10 for the delivered delta
**Scope:** read-only analysis of the selected-VM detail pane (`#detail-box`)
**Phase rule honoured:** no production or test code was modified for this report. The only
executable step was a read-only import/parse of the repository's own XML/text fixtures.
**Baseline:** branch `arena/86ec82cd-plaivid-cli`, commit `ad52ed2`, 351 unit tests green.

Findings are labelled:

| Label | Meaning |
| --- | --- |
| **source-verified** | Code path read in this repository; where noted, exercised against repo fixtures |
| **documentation-only** | Stated in `docs/SBELL-SABAD.md` / `docs/Plaivid CLI & sbell Reference.md`, not verified against a live host |
| **unverified** | Plausible but requires a real PVM host, captured dump, or manual check |

---

## 1. Executive summary

| Issue | Root cause (one line) | Fix class |
| --- | --- | --- |
| `Disks / NICs`, `Topology`, `Machine` are low value | They exist only on the **asynchronous** `VMDetail` (Enter read), are not in the base inventory, and their absence-degradation is misleading (`0 / 0` and `?x?x?` look like readings) | Renderer-only deletion; model fields stay for CLI/JSON |
| `Host` is missing | The pane renders `detail.host`, and `detail` is `None` until Enter **and** `ObjectVM` (the inventory read model) never captures `cluster/host`, so the field is `—` for every row before Enter — and for rows whose object has no `<host>` afterwards | Model + parser + renderer (no new I/O) |
| Console `PORT` is missing | Not a data gap: three parsed sources already exist (`ConsoleInfo.port`, dead `ObjectVM.configured_port`, live `ProcessObservation.port`). The renderer simply never shows a port, only `detail.console.kind` | Renderer + small model/read-model wiring; fallback already wrapped |

The two "missing" fields are **presentation gaps**, not collection gaps. Neither the host nor
the port requires a new `sbell` command or a new subprocess.

---

## 2. How the pane gets its data

```
sbell user/objects  ──► parse_object_inventory ──► ObjectVM ×N ─┐
                                   │                            ├─► merge_inventory (UUID join)
pvm-running-vms ─────────► parse_process_rows ──► ProcessObservation ×N ┘        │
                                                                                ▼
                                                                    InventoryData.records: VMRecord
                                                                                │  (fleet refresh)
                                                                                ▼
                                                       selection._render_record(record)
                                                                                │
                                     Enter ──► application.detail(token, uuid) ─┤
                                               sbell user/objects (per UUID)    │
                                               parse_vm_detail ──► VMDetail     ▼
                                                                    build_vm_detail(record, detail)
                                                                       └─ _pairs_grid(...)  → #detail-box
```

| Step | Evidence |
| --- | --- |
| Batch read = `user/objects` query + `pvm-running-vms` | `application/collection/reader.py:55-100` (**source-verified**) |
| Object parse, incl. `configured_port` | `infrastructure/pvm/parsers/inventory.py:29-70` (**source-verified**) |
| Process parse, incl. `port` | `infrastructure/pvm/parsers/inventory.py:75-150` (**source-verified**) |
| UUID join, `state_disagreed` | `domain/inventory.py:15-75` (**source-verified**) |
| Enter → detail read | `presentation/tui/app.py:106` (binding), `selection.py:246` (`action_details`), `:209` (`_load_detail`), `:222` (`_publish_detail`), `:182` (`_render_record`) (**source-verified**) |
| Detail parse | `infrastructure/pvm/parsers/vm_detail.py:21-114` (**source-verified**) |
| Rendering | `presentation/tui/pages/virtual_machines/components/details.py:85-113` (`_pairs_grid`), `:126-165` (`build_vm_detail`) (**source-verified**) |

**Design consequence already in the code:** `_pairs_grid` deliberately passes `None` for every
detail-owned field while `detail is None` ("detail-only fields stay absent until Enter", docstring
at `details.py:87`). The fleet refresh never loads a detail for the selected row, so on first paint
**every `VMDetail`-owned value is `—`**. Only `Object state`, `PID`, `Memory`, `Process`, `vCPU`
and the description are inventory-backed.

---

## 3. Finding 1 — the three low-value fields

### 3.1 Exact removal inventory

All three are **detail-only** (async `Enter` read). None of them comes from the base inventory.

| UI label | Render site | Value expression | Domain field | Parser / XML path | Evidence class |
| --- | --- | --- | --- | --- | --- |
| `Machine` | `details.py:95`; label tuple `_LEFT_LABELS` at `details.py:33` | `_value(detail.machine if detail else None, …)` | `VMDetail.machine` (`domain/models/host.py:93`) | `parsers/vm_detail.py:107` ← `virtual_machine/hardware/emulated_machine/type` | **repository evidence only** — path comes from retired `legacy/vms.py:309`; it is **not** in the documented object field table (`docs/SBELL-SABAD.md:231-240`) and the object fixture has no such element (parsed `None`) |
| `Topology` | `details.py:96`; label tuple `:33` | `_value(detail.vcpu_topology if detail else None, …)` | `VMDetail.vcpu_topology` (`host.py:90`) | **Synthesised** at `parsers/vm_detail.py:104` as `socket x core x thread`, with `?` for unknown parts | Inputs are documented (`hardware/cpu/vcpu/{socket,core,thread}`, `SBELL-SABAD.md:238`); the rendered string is app-generated |
| `Disks / NICs` | value built at `details.py:89`, row at `details.py:94`; label tuple `:34` | `f"{len(detail.disks)} / {len(detail.nics)}"` when detail exists | `VMDetail.disks: tuple[DiskInfo, …]`, `VMDetail.nics: tuple[NicInfo, …]` (`host.py:95-96`) | `parsers/vm_detail.py:59-77` ← `hardware/disk_manager/disk_list/disk`, `hardware/net_adaptor_list/net_adaptor` | **repository evidence only** — not in the documented field table; only present in legacy code + this parser |

Supporting dataclasses: `DiskInfo` (`host.py:49`), `NicInfo` (`host.py:58`).

### 3.2 Why they are low value (and actively misleading)

1. **They are invisible when they matter least.** Because they are detail-only, a user who never
   presses Enter sees `—` in all three rows. They add three lines of noise to the default view.
2. **`Topology` fabricates a value when data is missing — the only field in the pane that does.**
   `parse_vm_detail` builds `"x".join(part if part is not None else "?" …)`, so a VM object with no
   `<vcpu>` block renders the literal string `?x?x?` while the section status is `CURRENT`. That
   violates the project's rule that absent values render as `—` and never as invented data.
3. **`Disks / NICs` cannot distinguish "no devices" from "not captured".** With no `<disk_list>`
   element the parser yields `()`, and the pane renders `0 / 0` — a plausible-looking reading with
   no supporting evidence. It is also the only row whose value is a derived count rather than a
   PVM fact.
4. **`Machine` is a chipset string, not a host.** It is easily mistaken for the physical host — the
   very field the pane gets wrong. `machine` is also absent from the documented object schema, so on
   a real host it is likely to be `—` as often as not (**unverified**).
5. None of the three supports an interaction (no drill-down, no copy, no action). `CPU model` and
   `vCPU`, which remain, already describe the compute shape more usefully than `Topology`.

### 3.3 Other dependents (do not break these when deleting rows)

| Dependent | Location | Action |
| --- | --- | --- |
| CLI human detail text | `presentation/cli/reads.py:141` (`machine`), `:147` (`topology`), `:152` (disk/NIC counts) | **Out of scope of the UI deletion.** Decide separately; deleting the CLI lines is a behaviour change for `plaivid detail` and needs its own approval |
| JSON `detail` payload | `presentation/cli/serialization.py:53-80` (`asdict` over `VMDetail`) | Unchanged; removing rows removes nothing from JSON |
| TUI renderer tests | `tests/unit/test_vm_detail_panel.py:142-156` (label presence for all three) and `:194-199` (value assertions `pc-q35-6.2`, `4/1/1`, `2 / 1`) | Must be rewritten in the same commit |
| Parser tests | `tests/unit/test_pvm_parsers.py:90-125` | No change required (no assertions on `machine`, `vcpu_topology`, disks or NICs) |
| Brain docs | `docs/brain/contracts/DATA_MODELS.md:14-15`, `docs/brain/codebase/FILE_CATALOG.md:132` | No field removal, so no doc change needed; only the pane description in `FEATURE_TO_FILE_MAP.md:159` stays valid |
| Prior RCA | `docs/TUI_VM_DETAIL_PANE_RCA.md:295,317` | Historical; superseded by this report, leave as-is |

**Disposition:** delete the three rows and the three labels from `_LEFT_LABELS`; keep
`VMDetail.machine`, `.vcpu_topology`, `.disks`, `.nics` and their parsers so the CLI and JSON stay
intact. `_LEFT_WIDTH` is derived from `_LEFT_LABELS`, so it shrinks automatically (15 → 14 for the
remaining left column) and the alignment test keeps working.

> Optional clean-up, separate decision: `parse_vm_detail` returns `CURRENT` when the
> `virtual_machine` element is missing (it substitutes an empty element at `:45-46`). That is what
> makes `?x?x?` possible and also silently blanks `host`. Returning `PARTIAL` with a quality issue
> in that case is a parser-quality fix worth its own change; it is not required to remove the rows.

---

## 4. Finding 2 — missing `Host`

### 4.1 End-to-end trace

| Layer | Code | Behaviour |
| --- | --- | --- |
| Base inventory parse | `parsers/inventory.py:39-70` | Reads `uuid`, `name`, state, vcpu, memory, description, `hardware/console/port`. **Never reads `cluster/host`.** `ObjectVM` has no host field (`domain/models/inventory.py:11-25`) |
| Read model | `domain/inventory.py:52-67` | `VMRecord.object` is that hostless `ObjectVM` |
| Renderer | `details.py:102` | `("Host", _value(detail.host if detail else None, …))` → `—` whenever `detail is None` |
| Async detail | `parsers/vm_detail.py:94` | `host=machine.findtext("cluster/host")` → `VMDetail.host` (`host.py:80`) |
| Detail publish | `selection.py:222-241` | Only publishes if the UUID still matches; otherwise the row shows `—`/error |
| CLI parity | `reads.py:139` | `Host {detail.host or '—'}` — same async limitation |

Empirical check against the repo fixtures (**source-verified**, read-only):

```
inventory: 481e458c-… test-vm   configured_port=5900  has host attr: False
detail:    host='node-a'  console=ConsoleInfo(kind=None, port=5900, …)  machine=None
           topology='1x4x1'  disks/nics=0 0
```

So the XML parser *does* extract the host when the element exists (fixture `objects.xml` carries
`<host>node-a</host>`), but the inventory read model has nowhere to put it.

### 4.2 Why the field is empty — four distinct causes

1. **Primary (affects every row):** the value is detail-only. Before Enter, `detail` is `None` and
   the renderer intentionally shows `—`. The base inventory never carries a host, so there is no
   earlier value to show. **This alone explains "Host is always missing".**
2. **`ObjectVM` shape:** even after the inventory read, the parsed host is discarded. This is a
   read-model gap, not a parsing gap.
3. **Legitimately empty objects:** a VM that is not assigned to a node (or a stopped/undefined
   placement) may return `<host/>` or no element. `_present()` maps `""`/`None` to `—`, which is
   correct — but it also means "not assigned" and "not read yet" look identical.
4. **No whitespace normalisation:** `findtext("cluster/host")` is stored verbatim. `_present()`
   replaces newlines/tabs but does not strip, so a padded value would render as a blank-looking
   cell rather than `—`. Cheap fix in the new parser/model path.

Additional nuance: `cluster/host` is documented as the node the VM *runs or belongs on*
(`SBELL-SABAD.md:237`). It is a placement fact, not proof of liveness, and `vm/start` accepts the
literal value `auto` in the same element (`SBELL-SABAD.md:129`). If a real host ever returns `auto`
or a numeric node id, the pane must show it **verbatim** rather than translate it (**unverified**
which form PVM 7.1.26 returns; the fixture uses the node name `node-a`).

### 4.3 Does `sbell` natively report the host/node?

**Verdict: yes, but only as an object-store field — and it describes placement, not liveness.**

| Capability | Command | Field | Status |
| --- | --- | --- | --- |
| VM → node assignment | `sbell user objects '<params><query>/objects/object/pvm_vmm_obj…</query></params>'` | `virtual_machine/cluster/host` | **documentation-only** (`SBELL-SABAD.md:237`) + **source-verified** parser/fixture |
| This node's identity | `sball/show` | `cluster/node/{id,name,ip}` | **documentation-only** (`SBELL-SABAD.md:258-271`) + **source-verified** parser `parsers/host.py:29-62`; fixture `sball-show.xml` → `name=node-a`, `id=1` |
| This node's hostname / OS / kernel | `monitoring/system` | `system_info/host_name`, platform, kernel | **documentation-only** (`SBELL-SABAD.md:271-273`) + **source-verified** parser `parsers/host.py:118-119,219-226` |
| VM → node via a running-process listing | `pvm-running-vms` | — | **Not available**: the table has 8 columns, none is a host (`SBELL-SABAD.md:250-256`, `Plaivid CLI & sbell Reference.md:136`) |
| Cluster-wide node inventory / VM-per-node listing | `sball/master` | — | Only listed in the module catalogue (`Plaivid CLI & sbell Reference.md:90`); no response shape or usage in the repo — **unverified, do not rely on it** |
| Migration input | `vmmigrate/run`, `vm/start` | `<host>` is a **parameter** | Direction is into PVM, never a read |

**Which module/command/response field to use:** `user/objects` (module `user`, command `objects`)
→ `pvm_vmm_obj/virtual_machine/cluster/host`. It is the same single call the inventory already
makes; adding the field costs **zero extra subprocesses** and no extra permissions. The closest
additional signal is `pvm-running-vms` presence, which proves a process exists on *this* host but
does not name the node.

### 4.4 Options considered

| # | Data path | Freshness | Cost | Invents values? | Verdict |
| --- | --- | --- | --- | --- | --- |
| A | Add `ObjectVM.host` ← `cluster/host` in the existing batch parse | every fleet refresh | none (same XML) | No | **Recommended primary** |
| B | Keep `VMDetail.host` (Enter) | on demand | one extra `user/objects` per Enter | No | Keep as confirmation/upgrade |
| C | If A and B are empty but `record.process_seen`: show `this node` (muted) | every fleet refresh | none | No — process evidence is local by construction | **Recommended fallback, labelled** |
| D | Resolve the local node name via `sball/show` (`HostStatus.name`) or `monitoring/system` (`HostMetrics.hostname`) and show it when the VM is provably local | needs a new collection section on the Fleet tab | extra `sbell` call per refresh (or a cached, low-cadence read) | No, but it asserts "this node == that name"; only safe when the VM is observed locally | Defer; requires a **separate** refresh-demand decision (Fleet currently collects only `inventory`, `refresh.py:110-125`) |
| E | Show `cluster_status/qemu_version`, `ha`, `enabled` as a pseudo-host | — | — | **Yes** | Rejected |

Option D is the only one that can put a *name* on a locally-running VM whose object has no host.
It must not be added to the 3-second fleet loop; a cached, on-demand or 60-second read is the only
acceptable shape. Until then, `this node` is the honest label.

### 4.5 Recommended Host resolution

```
host = record.object.host                       # A: native sbell, every refresh
    or (detail.host if detail else None)        # B: same XML, fresher read
    or ("this node" if record.process_seen else None)   # C: proven local existence, labelled
render: _value(host) → "—" when none
```

Plus one guard worth adding with it: if a host value is known **and** `record.process_seen` is true
**and** the value is provably not the local node, the object store and the local process table
disagree. That is a data-quality fact, not a display choice; surface it the way `state_disagreed`
is surfaced (a warning line), or leave it out until local node identity is available. Do not
silently pick one.

Model change is additive and default-safe: `ObjectVM.host: str | None = None`, normalised
(`strip() or None`). `merge_inventory` copies the object through untouched, so `record.object.host`
reaches the pane with no join change.

---

## 5. Finding 3 — missing console `PORT`

### 5.1 Three already-parsed sources

| Source | Field | Produced at | XML / output | Currently read by |
| --- | --- | --- | --- | --- |
| Native object store (batch) | `ObjectVM.configured_port` | `parsers/inventory.py:54,63` ← `hardware/console/port` | object XML | **nothing** (dead field: only definition + assignment) |
| Live host process table | `ProcessObservation.port` | `parsers/inventory.py:96-120` ← `PORT` column | `pvm-running-vms` | **nothing** in presentation; only `merge_inventory` carries it to `VMRecord.process.port` |
| Async detail read | `ConsoleInfo.port` (with `kind`, `bind_address`, `password_enabled`, `tls`) | `parsers/vm_detail.py:79-88` ← same `hardware/console/port` | object XML | CLI JSON; **not rendered** |

**Root cause:** the renderer prints `detail.console.kind` only (`details.py:90`) and no port
anywhere. The port is not missing — it is *unrendered*, and the two non-detail paths were wired up
and then never consumed. The `Console` row also shows `—` for every fixture VM because the fixture
object has `<console><port>` but no `<type>`.

Empirical check (**source-verified**): same VM yields **configured 5900** and **live 5901** in the
repo fixtures. Configured and live ports are *different facts*; whichever is displayed must be
labelled or chosen by a documented rule.

### 5.2 Is the `pvm-running-vms` fallback already wrapped?

**Yes, completely — no new subprocess, parser, or permission is needed.**

| Concern | Existing implementation | Assessment |
| --- | --- | --- |
| Invocation | `LocalPvmAdapter.list_processes` (`adapter/local.py:180-215`), argv from `PLAIVID_RUNNING_VMS` (default `pvm-running-vms`), `config.py:93` | **source-verified** |
| Scheduling | `application/collection/reader.py:55-100` reads it inside the `inventory` section; TUI collects `inventory` every fleet refresh (`refresh.py:108-120`) | **source-verified** |
| Match key | Canonical **UUID**, in both parsers (`canonical_uuid`) and `merge_inventory` (`domain/inventory.py:26-50`); process-only rows are excluded from `records`, duplicates excluded with a quality issue | **source-verified** — this is exactly the required key |
| Running-only | Rows exist only for live hypervisor processes; paused VMs keep their process, stopped/`off` VMs have none | **documentation-only** semantics + **source-verified** merge comment (`domain/inventory.py:57-58`) |
| Local-only | The helper is a host binary invoked with no remote transport; there is no path in this repo to query another node | **source-verified** for our code; "local" **unverified** for the binary's own semantics (implied by name and PVM docs) |
| Parsing stability | Strict 8-column regex `_OBJECT_RE` (`parsers/inventory.py:19-22`), ANSI strip, header/title/`Total VCPU`/`Total Memory` handling, contiguity + vCPU-sum validation; any mismatch ⇒ `PARTIAL` + quality issues (`:120-170`) | **source-verified** — strict, self-reporting, fails closed |
| Permissions | Documented as read-only, no auth, no root (`SBELL-SABAD.md:246`); the app runs it under a restricted child environment (`ProcessRunner`, `infrastructure/process.py:105`) | **documentation-only** + **source-verified** env restriction |
| Timeout | `PLAIVID_CMD_TIMEOUT` default 30 s (`config.py:94`); runs in a worker thread, never the UI thread | **source-verified** |
| Redaction | Port is an integer; no secret content. Existing `_value`/`redact_text` path applies anyway | **source-verified** |
| Partial / stale data | On a partial process read, rows that did parse are still merged; the section status becomes `PARTIAL` and the record may carry `state_disagreed`. The pane today renders no per-value provenance | **source-verified** |

Two caveats worth recording for the implementation phase:

1. **The PORT column is mandatory in the regex.** `_OBJECT_RE` requires `(\d+)` for PORT, VCPU and
   MEMORY; a row where PVM prints a dash or blank in any of those columns is dropped *entirely*
   (`"unrecognized running-process row excluded"`), losing PID and uptime too. Whether PVM ever
   prints a non-numeric port is **unverified**; if it does, the "fallback" would silently vanish
   for that VM. Do not loosen the regex speculatively — capture a real row first.
2. **Detail freshness is not tracked.** `_detail_loaded` is cleared on UUID change only
   (`selection.py:182-189`); the same row keeps its `VMDetail` across inventory refreshes and has
   no section generation. Inventory-derived values (live port, configured port) are therefore
   *fresher* than `detail.console.port` for a long-lived selection.

### 5.3 Recommended PORT resolution

The two paths are not substitutes — they answer different questions:

* `configured_port` = the port PVM has assigned to the VM's console (**configuration**).
* `process.port` = the port the running hypervisor process actually bound (**live binding**).

Recommended display order, with the value's origin visible:

| Priority | Value | When available |
| --- | --- | --- |
| 1 | `record.process.port` (+ muted `live`) | VM observed by `pvm-running-vms` on this host |
| 2 | `record.object.configured_port` (+ muted `configured`) | every inventory read |
| 3 | `detail.console.port` | after Enter, only if 1 and 2 were both absent |
| 4 | `—` | none of the above |

Notes:

* Priority 1 answers "what can I connect to right now"; priority 2 answers "what is it configured
  to use". Showing the live value first prevents a user from trying a stale configured port on a
  running VM.
* The provenance marker is optional (product decision). If omitted, use priorities 1 → 2 → 3
  anyway, and never display a configured value as if it were live.
* `detail.console.port` is redundant with priority 2 (identical XML path, older snapshot). Keeping
  it as a last resort costs nothing and preserves behaviour when the batch read is partial.
* If the pane should also show console *kind*, keep the existing `Console` row and add a separate
  `Console port` row, rather than overloading one cell with two facts.
* Never derive a port from PID, bind address, or a "next free" guess.

---

## 6. Cross-cutting observations

1. **The pane hides the provenance of every value.** A number from the object store, a number from
   a local process table, and a number from a detail read all look identical. For Host and Port —
   the two fields with multiple legitimate sources — a short qualifier (`live`, `configured`,
   `this node`) is cheap and prevents wrong operational conclusions.
2. **`state_disagreed` is the only conflict surfaced.** Host and port can disagree the same way
   (object says node-X, local process exists; configured 5900, live 5901). The state-conflict idiom
   at `details.py:155-159` is the right pattern to extend if conflict surfacing is wanted.
3. **Row count and pane height stay bounded.** Current grid: 6 rows (left) vs 5 (right). Removing
   three rows and adding one port row leaves 5 rows; `#detail-scroll` is capped at `max-height: 12`
   (`styles.py:130`) with `#detail-box { min-height: 9 }` (`styles.py:132`), so the Audit panel keeps
   its space. No CSS change is required, but the layout must be re-rendered once to confirm.
4. **The parser's "missing `virtual_machine`" behaviour is a latent trap** (§3.2): detail status is
   `CURRENT` with an empty hardware block. Once `Topology` is removed, the visible symptom
   disappears and the trap becomes silent. Fix it deliberately, with a test.
5. **No local node identity is available to the Fleet tab today.** `host_status` / `host_metrics` /
   `local_host` are collected only for the Overview tab (`refresh.py:122-145`), and the Fleet tab's
   periodic path requests `inventory` alone (`refresh.py:108-120`). Any Host design that needs a
   node *name* must argue for that extra read explicitly.

---

## 7. Implementation plan (next phase)

### Phase A — remove the three low-value rows (renderer only)

| File | Change |
| --- | --- |
| `presentation/tui/pages/virtual_machines/components/details.py` | Drop `Machine`, `Topology`, `Disks / NICs` from `_LEFT_LABELS` (`:33`) and from the `left` tuple (`:91-97`); delete the `disks_nics` expression (`:89`) |
| `tests/unit/test_vm_detail_panel.py` | Update the label-presence list (`:142-156`) and the value assertions `pc-q35-6.2` / `4/1/1` / `2 / 1` (`:194-199`); add a negative test: the rendered pane contains none of the three labels |
| `tests/unit/test_cli_and_tui.py`, `test_tui_theme.py` | Only if their text scans mention the removed labels (currently they do not) |

Keep `VMDetail.machine`, `.vcpu_topology`, `.disks`, `.nics` and their parsers. Keep the CLI lines
unchanged unless a separate decision is taken.

### Phase B — Host from the object store (no new I/O)

| Layer | File | Change |
| --- | --- | --- |
| Model | `domain/models/inventory.py` | Add `ObjectVM.host` (optional, default `None`); normalise `strip() or None` in `__post_init__` |
| Parser | `infrastructure/pvm/parsers/inventory.py` | `host=()` `machine.findtext("cluster/host")` with the same guard used for state/vcpu/memory (`machine is not None`) |
| Renderer | `details.py` | Host value = `record.object.host or (detail.host if detail else None) or ("this node" if record.process_seen else None)`; append a muted qualifier for the local case |
| Domain join | `domain/inventory.py` | None (object passes through) — verify with a test |
| Tests | `tests/unit/test_pvm_parsers.py` | inventory parse yields `host == "node-a"`; absent `<host>` → `None`; `<host> auto </host>` → `"auto"` verbatim (no translation) |
| Tests | `tests/unit/test_domain_models.py` | `ObjectVM` default `host is None`; immutability preserved |
| Tests | `tests/unit/test_vm_detail_panel.py` | Host renders from the record **without** a `VMDetail`; `—` when unknown; `this node` only when `process_seen`; redaction still applied |
| Tests | `tests/unit/test_multi_select.py` / collection test | `record.object.host` survives `merge_inventory` |
| Docs | `docs/brain/contracts/DATA_MODELS.md`, `API_CONTRACTS.md` (inventory JSON now carries `object.host`) | Add the field, note it is a placement fact |

Decision required: whether a locally-running VM with no `cluster/host` shows `this node` (labelled)
or `—`. Recommendation: `this node`, because it is proven by local process evidence and invents no
name.

### Phase C — Console port from existing sources

| Layer | File | Change |
| --- | --- | --- |
| Renderer | `details.py` | Add a `Console port` row; implement the 1→4 order of §5.3 in a small pure helper (e.g. `_console_port(record, detail)` returning the port plus its qualifier) so it is testable in isolation |
| Model | `domain/models/inventory.py` | None — `configured_port` and `process.port` already exist |
| Presentation | `selection.py` | None; the record already carries both values pre-Enter |
| Tests | `tests/unit/test_vm_detail_panel.py` | live wins over configured; configured used when no process; `—` when neither; detail-only value used last; qualifier text present; no `VMDetail` needed for the first two cases |
| Tests | `tests/unit/test_pvm_parsers.py` | Configured and live ports both parsed from the existing fixtures (already true; add the invariant that they differ in the fixture so the precedence test is meaningful) |
| Docs | `docs/brain/contracts/DATA_MODELS.md` | Document that `ObjectVM.configured_port` is now consumed (it is currently dead) |

Optional (separate approval): parser-quality fix returning `PARTIAL` when
`virtual_machine` is missing, with a quality issue and no `?x?x?` topology.

### Phase D — verification

1. `pytest tests/unit` — 351 baseline, expected +6 to +8 new assertions/tests, zero failures.
2. `ruff check .` clean (line length 100).
3. Render the pane at 80 and 120 columns to confirm alignment, no truncation of the full UUID, and
   that the Audit panel stays visible with the new row count.
4. Run `scripts/validate_brain.py` after any `docs/brain` edit.
5. Update this report's status line and `docs/TUI_VM_DETAIL_PANE_RCA.md` cross-reference if the
   layout description changes.

### Out of scope

* Any change to `pvm-running-vms` parsing (regex, columns, error handling).
* Any new `sbell` command (`sball/master`, `monitoring/system`) on the Fleet tab.
* CLI human output for `plaivid detail`.
* Removing `VMDetail` fields themselves.

---

## 8. Risks and open questions

| # | Risk / question | Mitigation |
| --- | --- | --- |
| 1 | `cluster/host` may be a numeric node id or `auto` on a real cluster (**unverified**) | Show the raw value; do not translate. Only map id→name if a real response proves the id form *and* a node inventory exists |
| 2 | `this node` could be misread as a hostname | Render it muted/quoted (`this node`) and only when `process_seen` |
| 3 | Live port may belong to a VM the user is not looking at, if UUID correlation ever regresses | Correlation is by canonical UUID in both layers, with duplicates excluded and unmatched rows dropped; keep the existing tests as guards |
| 4 | A dropped process row (non-numeric PORT) hides both PID and live port | Capture a real `pvm-running-vms` dump before touching `_OBJECT_RE`; the parser fails closed and reports `PARTIAL`, so the pane shows `—` rather than a wrong number |
| 5 | Detail staleness across refreshes | Do not rely on `detail.console.port` for running VMs; prefer inventory-derived values |
| 6 | `object.host` in JSON changes the documented payload shape | Additive field with a default; announce it in `docs/brain/contracts/API_CONTRACTS.md` |
| 7 | PVM 7.1.26 real responses still unvalidated in this repo | Everything above that touches real output is documentation-only; the implementation must not assert real-host behaviour in tests or docs |

---

## 9. Evidence appendix

Line references below are relative to the audit baseline commit `ad52ed2`; later edits can
shift them, so treat symbol names as the durable reference.

**Read-only fixture run** (`PYTHONPATH=. python3`, no writes; fixtures `tests/fixtures/objects.xml`,
`tests/fixtures/running-vms.txt`):

```
inventory: 481e458c-c6ba-4fe7-88f6-26a59e416568 test-vm state=started configured_port=5900
           has host attr: False
inventory: 2b8ec16f-c2db-43d9-b65c-12077dbdc5b8 offline-vm state=stopped configured_port=None
detail:    host='node-a' console=ConsoleInfo(kind=None, port=5900, bind_address=None,
           password_enabled=None, tls=None) machine=None topology='1x4x1' disks/nics=0 0
process:   481e458c-… test-vm pid=1234 port=5901
process:   81f3fa0b-… process-only pid=9999 port=5902   (no matching object → excluded)
```

**Key source references**

* `details.py:33-34` label tuples; `:85-113` `_pairs_grid`; `:126-165` `build_vm_detail`; `:175` `#detail-box`
* `domain/models/inventory.py:11-25` `ObjectVM` (+`configured_port`), `:31-45` `ProcessObservation` (+`port`), `:48-72` `VMRecord`
* `domain/models/host.py:67-73` `ConsoleInfo`, `:76-100` `VMDetail`
* `parsers/inventory.py:19-22` `_OBJECT_RE`, `:54,63` configured port, `:100-115` process row
* `parsers/vm_detail.py:45-46` empty-`virtual_machine` substitution, `:59-77` disks/NICs, `:79-88` console, `:94` host, `:104` topology synthesis
* `domain/inventory.py:15-75` UUID correlation
* `adapter/local.py:166` `list_objects`, `:180-215` `list_processes`, `:220-225` `vm_detail`
* `adapter/requests.py:23-26` `VM_QUERY`
* `selection.py:182-260` detail read model and Enter handling; `app.py:106` Enter binding
* `refresh.py:110-140` Fleet vs Overview section demand
* `presentation/cli/reads.py:141,147,152`; `serialization.py:53-80`
* `docs/SBELL-SABAD.md:231-273` object field table, `pvm-running-vms`, `sball/show`, `monitoring/system`
* `docs/Plaivid CLI & sbell Reference.md:90` module catalogue, `:136` `pvm-running-vms` columns
* Tests: `test_vm_detail_panel.py:48-83` fixtures, `:115-199`; `test_pvm_parsers.py:90-125`; `test_domain_models.py:28`

---

## 10. Implementation outcome

Delivered on `arena/86ec82cd-plaivid-cli` on top of `ad52ed2`.

| Area | Change |
| --- | --- |
| Native Host | `ObjectVM.host` (verbatim `cluster/host`, blank normalised to `None`), parsed in `parse_object_inventory`; `VMRecord.host` exposes it; the pane renders `record.host or detail.host`, decorated with the local hostname (`node (hostname)`) only when the node is proven local |
| Console Port | `resolve_console_port(record, detail)` in `domain/models/inventory.py` (live process → configured object → detail console → `None`); `Console` renders `<kind> : <port>`, `—` when neither is known |
| UI cleanup | `Machine`, `Topology`, `Disks / NICs` rows and labels removed; grid is now `Object state / PID / Memory / Console` (left) and `Process / vCPU / Host / Description` (right) |

Deltas from the plan in §7, explicitly requested for this phase:

* `CPU model` is also gone (it was not in the approved field set), so `EPYC 7443`-style model
  strings no longer appear in the pane; `VMDetail.cpu_model` and the CLI JSON still carry them.
* `Description` moved from a full-width row into the grid's flexible right column. It folds rather
  than clips (the fourth grid column is the only non-`no_wrap` column), which keeps the pane within
  `#detail-scroll`'s `max-height: 12`.

Verification: `pytest tests/unit` → 358 passed; `ruff check .` clean; `scripts/validate_brain.py`
passes. One earlier full run hit the known timing-sensitive
`test_virtual_desktops.py::test_page_search_uuid_selection_and_direct_action[80]` case, which
passes in isolation and is unrelated to this change. The CLI detail output and JSON payloads are
unchanged apart from the additive `object.host` field.
