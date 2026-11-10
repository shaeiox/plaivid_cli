# RCA — Virtual Machines detail pane (`#detail-box`)

**Scope:** audit and subsequent refactor of the selected-VM details pane in the Textual TUI.
**Revision audited:** `3e630fe` (`Bump version to 1.5.0`); refactor on branch
`arena/86ec82cd-plaivid-cli`.
**Status:** implemented — §1–§8 are the pre-change audit that drove the refactor; §9 records what
shipped and how it was verified. Findings came from source inspection plus an isolated probe of the
same widget/CSS/string in a throwaway venv (Textual 8.2.8; `textual>=0.47` is the declared floor,
so both the 0.47 and 8.x behaviour were checked).

---

## 1. Verdict

The pane is not a "broken renderer". It is a **plain `Static` that receives one flat
`str` built by f-strings**, and `redact_text()` returns `str`, so the widget has nothing to style:
one unspanned `Text` object. No Rich renderable is ever constructed for this pane, no palette is
handed to it, and the state-colouring helper that the table already uses is simply never called.
The panel then hides part of its own content because its CSS height (10 cells) is smaller than the
text it is given (7–10 lines).

Ranked causes:

| # | Cause | Evidence |
|---|---|---|
| **C1** | Colour/emphasis is never applied — a single `str` is passed to `Static.update()` | `selection.py:165-175`, `selection.py:189-198` |
| **C2** | No structured renderable: no `Text`/`Table`/`Group`, no per-value styling, no label column | same |
| **C3** | Widget is a generic `Static` with `markup=False`, no palette, no border title, no scrolling | `components/details.py:6-10`, `styles.py:128-129` |
| **C4** | The existing state-colour source (`theme.state_text`) is not reused; conflict is a text suffix | `theme.py:174-193` vs `selection.py:166` |
| **C5** | Fixed-height box clips the content (base 7 lines, loaded 10 lines, 6 visible) | `styles.py:128`, probe below |

`markup=False` is **not** the root cause (see §4.1), but it does mean that adding `[red]…[/]`
strings would print literal brackets, so the phase-2 fix must use Rich objects, not Textual markup.

---

## 2. Where the pane lives

| Layer | File | Symbol | Lines |
|---|---|---|---|
| Widget | `plaivid_cli/presentation/tui/pages/virtual_machines/components/details.py` | `VMDetailPanel(Static)` — `id="detail-box"`, `markup=False` | 6–10 |
| Sibling widget | same file | `VMAuditPanel(Static)` — `id="audit-panel"`, same pattern | 13–17 |
| Composition | `plaivid_cli/presentation/tui/pages/virtual_machines/page.py` | `VirtualMachinePage.compose` yields `VMDetailPanel()` | 20–25 |
| Text construction | `plaivid_cli/presentation/tui/pages/virtual_machines/selection.py` | `VMSelectionMixin._render_record` | 165–175 |
| Text construction (2nd source) | same file | `VMSelectionMixin._publish_detail` | 189–198 |
| Event handler | same file | `VMSelectionMixin.row_highlighted` | 152–163 |
| Concrete re-declaration | `plaivid_cli/presentation/tui/app.py` | `PlaividTui.row_highlighted` (`@on(DataTable.RowHighlighted, "#fleet-table")`) | 429–431 |
| Style | `plaivid_cli/presentation/tui/styles.py` | `#detail-box` rule | 128–129 |
| Reset | `plaivid_cli/presentation/tui/session.py` | `_clear_session_view` | 108 |

Facts about the widget:

- It is a **plain `Static`**, no composition, no children, no `Vertical`/`VerticalScroll`.
- Its constructor takes **no palette**; the app's `_palette` never reaches it.
- `markup=False` (the repo convention — **zero** `markup=True` usages exist).
- It never receives a `border_title`; unlike `#vm-list`, which is branded through
  `group_title("vms", …)` in `app.py:171-181`.
- CSS: `height: 10`, `border: round $p-border`, `background: $p-panel`, `padding: 1`
  → **content area = 6 rows** (10 − 2 border − 2 padding).
- Not scrollable; Textual `Static` clips overflow.

The same defect exists on the Virtual Desktops page
(`virtual_desktops/components/details.py:15` + `controller.py:129-161`), which wraps its `Static`
in a `VerticalScroll` but still builds one flat f-string.

---

## 3. Data-binding trace

**Primary path (the one the question asks about):**

```
DataTable cursor moves
  └─ DataTable.RowHighlighted  (event posted by #fleet-table, CheckableTable)
       └─ PlaividTui.row_highlighted            app.py:429-431        # concrete @on(...) re-declaration
            └─ VirtualMachinesMixin.row_highlighted
                 selection.py:153                                    # guards: _running, is_mounted, _table_order
                 ├─ key = event.row_key.value → str(uuid)
                 ├─ self._selected_uuid = key
                 ├─ record = self._records[key]
                 └─ self._render_record(record)   selection.py:165
                      ├─ builds one f-string (7 lines)
                      ├─ caches it in self._detail_base          # a *string*, not a model
                      └─ query_one("#detail-box", Static).update(redact_text(detail))
```

There is no message/observer indirection: the mixin writes directly into the widget by selector.

**Secondary paths that also repaint the same widget:**

| Trigger | Path |
|---|---|
| Search text changes (`#vm-search`) | `vm_search_changed` → `_filter_vms` (`selection.py:94`) → `move_cursor` + explicit `_render_record` (or the "no matching VMs" string at 145–150) |
| "Apply to all VMs" toggled | `vm_scope_changed` → `_filter_vms` |
| Enter / `action_details` | `selection.py:200` → threaded worker `_load_detail` (178) → `call_from_thread(_publish_detail)` (189) → `Static.update(redact_text(self._detail_base + extra))` |
| Logout / session clear | `session.py:108` → plain reset string |
| Mount | the widget's constructor string |

Consequences of this binding:

- **Two independent text builders** (`_render_record` and `_publish_detail`) must be edited in
  lockstep; the async one *concatenates onto a cached string*, so any reformat of the base body
  silently breaks the loaded-detail body.
- The panel cannot tell the user that detail is loading, or that `_load_detail` failed: the worker
  swallows every exception (`except Exception: return`, `selection.py:185-186`). Pressing Enter on
  a slow/failed host produces **no visible change at all**.
- Repaint granularity is the whole widget; there are no child widgets/sections to update.

---

## 4. Why it is colourless and unstructured

### 4.1 `markup=False` is not the reason (verified)

`Static` with `markup=False` wraps a **`str`** in a plain `Text`; it does **not** strip styling from
a Rich renderable passed to `update()`. Probe on Textual 8.2.8 and source check on 0.47:

```
update("[bold red]stopped[/]")      → renders literally: "[bold red]stopped[/]"
update(Text("stopped", style="…"))  → Content, spans preserved: bold #ff87af
```

So the missing piece is the *renderable*, not the flag. This matters for phase 2: keep
`markup=False` (it is also an injection guard for PVM-supplied names/descriptions) and build
`Text`/`Table` objects instead.

### 4.2 The string builder

`selection.py:165-175`:

```python
state_conflict = " · STATE EVIDENCE CONFLICT" if record.state_disagreed else ""
detail = (
    f"{record.name}\nUUID  {record.uuid}\nObject state  {record.state}{state_conflict}\n"
    f"Process observed  {'Yes' if record.process_seen else 'No'}\n"
    f"PID  {_display(record.process.pid if record.process else None)}\n"
    f"vCPU  {_display(record.vcpu)}  ·  Memory  {_display(record.mem_mb, suffix=' MB')}\n"
    f"Description  {record.object.description or '—'}"
)
self._detail_base = detail
self.query_one("#detail-box", Static).update(redact_text(detail))
```

`_publish_detail` (`189-198`) appends three more `\n`-joined lines the same way.

Everything the pane lacks follows from this one line of design:

1. **No spans.** `redact_text()` is typed `-> str`; `Static.update(str)` produces one `Text` with
   no styles. There is nothing for Rich to colour.
2. **No alignment.** Values are separated by hardcoded `"  "` after labels of 3–12 characters, so
   values start at column 5 (`UUID`), 5 (`PID`), 14 (`Object state`), 18 (`Process observed`),
   14 (`Description`). The "two-column" `vCPU · Memory` is a coincidence of that particular row —
   it does not align with anything above or below.
3. **No hierarchy.** One flat block: no header, no sections, no rule, no label/value contrast.
   The record name and the UUID have the same weight as the PID.
4. **No semantics.** `stopped` / `STATE EVIDENCE CONFLICT` are inert words; the eye has no
   pre-attentive cue. The `·` separator is used both as a field separator and as part of a warning,
   so the warning is not distinguishable from ordinary punctuation.
5. **Vocabulary drift from the table.** The table says `Observed` / `Not observed`
   (`selection.py:105`); the pane says `Yes` / `No`. Memory is raw `8192 MB` with no grouping or
   unit humanisation, although the Overview already formats byte units (`overview_metrics/common.py:8`).
6. **No provenance.** Extra fields from the async detail read are appended without a separator or
   a "loaded from `detail:<uuid>`" marker; they visually merge into the base record.

### 4.3 The box clips itself (measured)

`#detail-box` = `height: 10`, `border: round` (2), `padding: 1` (2) → **6 usable rows**.

| State | Lines produced | Visible | Lost |
|---|---|---|---|
| Before Enter (base record) | 7 | 6 | `Description` |
| After Enter (base + `extra`) | 10 | 6 | `Description`, `Host`, `CPU model`, `Disks/NICs/console` |

Probe (same CSS, 80×24, string from `_render_record` + `_publish_detail`):

```
│ web-prod-01
│ UUID  1b4e28ba-2fa1-11d2-883f-0016d3cca427
│ Object state  stopped
│ Process observed  No
│ PID  —
│ vCPU  4  ·  Memory  8192 MB          ← content ends here (6 rows)
╰────────────────────────────────────  ← "Description", "Host", "CPU model", "Disks" are clipped
```

A long `description` or a long VM name wraps (`text-wrap` default) and hides even more. Because the
widget is not scrollable, the hidden fields are unreachable.

### 4.4 Secondary UI defects in the same pane

- No border title, so a user cannot tell the pane is "the selected VM" (the list above it *is*
  titled "VM list"); hierarchy is inverted — the list looks primary, the details anonymous.
- `state_disagreed` warning text is appended *inside* the state value, which makes any future
  state styling ambiguous (colour the state, or colour the warning?).
- `except Exception: return` in `_load_detail` gives no feedback on failure.
- The audit pane (`VMAuditPanel`) has the same flat-string construction and is likewise unstyled.

---

## 5. Colour palette mapping — what already exists and must be reused

The table is coloured today because the selection controller wraps the state cell in a Rich `Text`:

```python
# selection.py:90-92
def _cell_text(self, column: int, cell: str) -> Text:
    # Column 2 is the object state (VM page) or cluster status (Virtual Desktops page).
    return state_text(cell, self._palette) if column == 2 else Text(cell)
```

| Concern | Source of truth | Notes |
|---|---|---|
| Semantic colours | `presentation/theme.py` constants `SUCCESS #d7ffd7`, `WARNING #ffffaf`, `ERROR #ff87af`, `MUTED #a5a5ba`, plus `ALARM`/`CAUTION` for overview | 19–26, 168–170 |
| Palette variants | `Palette` dataclass + `TRUECOLOR` / `ANSI256` / `ANSI16` / `NO_COLOR` (`decorative=False`) | 29–80 |
| State classification | `_HEALTHY_STATES`, `_STOPPED_STATES`, `_TRANSIENT_STATES`; `state_text()` `→ rich.text.Text` | 174–193 |
| Table consumption | `VMSelectionMixin._cell_text` (VM state, column 2); the Desktop controller reuses the same helper for cluster status (column 2) | `selection.py:90`, desktop cells built in `controller.py:84-95` |
| Page identity | `GROUP_STOPS["vms"] = ("#ff87d7", "#ffafff")`, `group_title()`, `group_color()`; applied through `PlaividTui._group_box` | `theme.py:84-131`, `app.py:171-186` |
| CSS tokens | `$p-green/$p-rose/$p-yellow/$p-muted/$p-cyan/$p-blue` generated from `Palette.css_tokens()` | `theme.py:47-55` |
| In-repo precedent for label/value `Text` | `_host_status_text()` builds `f"{label:<8} : "` muted + redacted value, per-row styles | `overview/components/host_status.py:74-110` |

**Reuse target for badges:** call `state_text()`'s classification. To build a badge you need the
*colour*, not a pre-styled `Text`, so phase 2 should extract `state_colour(value, palette) -> str`
(and let `state_text()` delegate to it). That keeps a single classification table (no duplicated
frozensets in the details renderer) — the frozensets are the real contract, not the `Text` wrapper.

**Constraint from the palette:** `success`/`warning`/`error` are *light foreground tints*
(`#d7ffd7`, `#ffffaf`, `#ff87af`) intended for dark panels. They are high-contrast as text and as a
`●` marker, but they are poor *background fills* (light text on a light fill). The stylesheet also
deliberately reserves filled colour for keyboard focus. So the badge must be
**glyph + coloured word** (not a filled pill), and must stay readable in `NO_COLOR`, where the word
alone still carries the meaning.

---

## 6. Proposed structural strategy for phase 2

### 6.1 Options considered

| Option | Shape | Verdict |
|---|---|---|
| **A. Borderless Rich grid of styled `Text`, built by a pure renderer** | `Table.grid` (or `Group` of `Text`) → `Static.update()` | **Recommended.** Reuses `state_text`/`Palette`, aligns labels, works on 0.47 → 8.x, no new widget ids, consistent with the repo's Rich-first convention. |
| B. Textual-native composition (a `Vertical` of per-section `Static`s, `Horizontal` label/value pairs) | many small widgets | Rejected for now: more ids/CSS/tests, focus and repaint churn, and it diverges from every other panel (all Rich-in-`Static`). Worth revisiting only if per-field copy/selection is required. |
| C. Textual markup strings with `markup=True` | `"[bold red]stopped[/]"` | Rejected: breaks the repo-wide no-markup invariant, creates an injection surface through PVM names/descriptions, and still needs per-value redaction. |

### 6.2 Target structure

```
VMDetailPanel(Static, id="detail-box", markup=False)      # id and role unchanged
  ▲ receives a Rich renderable from a PURE builder
  └─ components/details.py
       def build_vm_detail(record: VMRecord,
                           detail: VMDetail | None,
                           palette: Palette) -> RenderableType
       def build_detail_placeholder(kind: Literal["empty","loading","error"], …) -> RenderableType
```

- The builder lives in `pages/virtual_machines/components/details.py`. That directory may import
  Rich, Textual, the theme **and `plaivid_cli.domain`**, but **not** `plaivid_cli.application`
  (`tests/unit/test_architecture_boundaries.py::test_tui_components_are_presentation_only_and_shared_table_is_unique`).
  `VMRecord`, `VMDetail`, `DiskInfo`, `NicInfo`, `ConsoleInfo` are all domain models, so this is legal
  and keeps the mixin thin.
- `VMSelectionMixin` keeps the *wiring* (`_render_record`, `_publish_detail`, `_filter_vms`,
  `action_details`) and only changes the terminal line from
  `update(redact_text(detail))` to `update(build_vm_detail(...))`.
- Delete the `self._detail_base: str` cache; keep the read model instead
  (`self._detail_record: VMRecord | None`, `self._detail_loaded: VMDetail | None`) so the base and
  the async extras are rendered together, once, by one function. This removes the
  "concatenate onto a cached string" bug class.
- `action_details` keeps its explicit Enter trigger (no auto-fetch on highlight — that would add
  `sbell` calls per arrow key and violate the repository's read-budget discipline), but the panel
  gains a muted footer hint `Enter · read full detail` and a `Loading detail…` / `Detail read
  failed` row so the worker's silence is no longer invisible.

### 6.3 Layout specification

Three bands, top to bottom:

1. **Identity** — VM name, bold.
2. **Warning band** — only when `state_disagreed` or `quality_issues` exist:
   `▲ state evidence conflict` / `2 quality issues` in `palette.warning`.
3. **Fields** — full UUID on its own line (never truncated), then the two-pair grid below.

Body: a **two-pair grid** (label/value × label/value), label column width derived from the label
set (`max(len(label)) + 2 = 14` for this field set), `no_wrap=True` on every cell except
`Description`, values right of the labels, `·` reserved for the *conflict* annotation only:

| Field | Label | Value style |
|---|---|---|
| `record.uuid` | `UUID` | foreground, `no_wrap` (full 36 chars; own row) |
| `record.state` (+ `state_disagreed`) | `Object state` | **`state_badge()`**; conflict → separate warning line, not glued to the state |
| `record.process_seen` / `process.pid` | `Process` / `PID` | badge (`● observed` / `○ not observed`) / foreground or `—` muted |
| `record.vcpu` | `vCPU` | accent (quantity) |
| `record.mem_mb` | `Memory` | accent, humanised (`8.0 GiB` or grouped `8 192 MB`), `—` when absent |
| `detail.host`, `detail.machine` | `Host` / `Machine` | foreground |
| `detail.cpu_model`, `detail.vcpu_topology` | `CPU model` / `Topology` | foreground |
| `len(detail.disks)`, `len(detail.nics)`, `detail.console.kind` | `Disks / NICs` / `Console` | accent / foreground |
| `record.object.description` | `Description` | muted, wrapped, last row |
| `record.quality_issues` | `Quality` | warning, only when non-empty |

Responsive rule (mirrors the existing `_set_width_class` idea rather than inventing a new one):

- **≥ 90 columns:** two pairs per row (as mocked below) → 13 fields in ~7 content rows.
- **< 90 columns:** one pair per row; UUID stays full-width, `Description` wraps last.
- Never truncate the UUID; if a value must be shortened (e.g. hostname), ellipsis it and keep the
  full value available via the detail read.

80-column preview (content width 74; rendered with Rich at that width in the probe):

```
web-prod-01
UUID           1b4e28ba-2fa1-11d2-883f-0016d3cca427

Object state   ● stopped             Process       ○ not observed
PID            —                     vCPU          4
Memory         8 192 MB              Host          node-7
Machine        pc-q35-6.2            CPU model     EPYC 7443
Topology       4/1/1                 Console       vnc
Disks / NICs   2 / 1
Description    —
```

Styling: name in bold `palette.foreground` (or the `vms` pink); labels `palette.muted`; state and
process badges via `state_badge()` / a muted `○` variant; quantities in `palette.accent`; absent
values (`—`) muted; `STATE EVIDENCE CONFLICT` as an extra warning line under the name, so the state
badge stays a clean health verdict.

Placeholder states get the same skeleton (so the panel never jumps height):
`Select a VM to inspect its details.` · `No matching VMs. Clear search to view the inventory.` ·
`Reading full detail…` (muted) · `Detail read failed · press Enter to retry` (error).

### 6.4 Badge specification (single source of truth)

```python
# presentation/theme.py  (next to state_text, which delegates to it)
def state_colour(value: str, palette: Palette = TRUECOLOR) -> str: ...

def state_badge(value: str, palette: Palette = TRUECOLOR) -> Text:
    colour = state_colour(value, palette)
    return Text.assemble(("● ", f"bold {colour}"), (value, f"bold {colour}"))
```

- Reuses `_HEALTHY_STATES` / `_STOPPED_STATES` / `_TRANSIENT_STATES`; no second mapping table.
- `markup=False` semantics are preserved (a `Text`, never a markup string).
- `Palette.decorative is False` (16-colour / `NO_COLOR`): the glyph is dropped or rendered muted
  and the **word remains** — colour is never the only carrier of meaning (already the rule in
  `theme.py` and `docs/TUI_UNSLOP_PLAN.md`).
- Process observation uses the same shape with `palette.muted` and `○` (neutral, not a health
  verdict) — `observed` must not look like `started`.
- The state-disagreement signal becomes its own row/line: `▲ state evidence conflict` in
  `palette.warning` (or `ERROR` if the product prefers alarm), keeping `record.state` unmodified.

### 6.5 Widget, CSS and redaction changes

| Change | Detail |
|---|---|
| Keep id contract | `#detail-box` must remain the `Static` that holds the body (tests, controllers, CSS, `session.py:108` query it by id) |
| Scroll wrapper | Add `VerticalScroll(id="detail-scroll")` around `VMDetailPanel` — identical to the Desktop page's `#desktop-detail-scroll`, so overflow is reachable instead of clipped |
| CSS | `#detail-scroll { height: 12; margin-top: 1; border: round $p-border; background: $p-panel; overflow-y: auto; }`; `#detail-box { height: auto; padding: 0 1; background: $p-panel; }` (drop the fixed `height: 10`/`padding: 1` that causes the 6-row clip) |
| Panel identity | Give the **scroll wrapper** a `border_title` via `group_title("vms", "Selected VM", palette)` in `on_mount` (same pink `vms` gradient as "VM list"); keep `#detail-box` borderless inside it |
| Redaction | `redact_text()` **each raw value before** wrapping it in `Text` (`redact_text(record.name)` etc.). Never pass a `Text` into `redact_text()`: it returns `str` and would discard spans. This keeps the MODULE_CONTRACTS rule "redaction must be applied to any new user-visible string" |
| Field formatting | reuse `components.formatting.display()` for `—`, extend with one `human_mb()`/`quantity()` helper if "8 192 MB" is adopted; do not fabricate zeroes |

### 6.6 Compatibility and risks

| Risk | Finding / mitigation |
|---|---|
| Textual floor 0.47 vs current 8.x | Both accept a Rich renderable in `Static.update()`; 0.47 keeps it as `_renderable`, 8.x wraps it in `RichVisual` (styles preserved — probed). Avoid `update(..., layout=False)`, which only exists in newer versions |
| Existing tests read `str(widget.render())` | `test_cli_and_tui.py:280,493,502`, `test_tui_theme.py:100,184`, `test_virtual_desktops.py:149`. A `Text`/`Group`-of-`Text` renderable still `str()`s to plain text; a `Table.grid` `str()`s to `RichVisual(…)` (probed) and **breaks them**. Either keep the top-level object a `Text`, or update the tests to use a type-aware `plain(widget)` helper. Decide before coding |
| `Table.grid` measurement | Column widths must include the label padding (a 14-wide label column clips `vCPU 4`), so use separate label/value columns or a computed label width — do not hardcode per-row padding |
| Long values at 80 columns | `no_wrap` on numeric/state cells; UUID full width; `Description` the only wrapped cell; verify with `table.virtual_size.width <= table.region.width`-style assertions (already used for `#fleet-table`) |
| Repaint cost | Every highlight calls `Static.update()` → full widget relayout. Acceptable today (6 rows). A taller grid with wrapping text can trigger relayout storms on arrow-key scrubbing; measure before/after |
| Colour-only signalling | Keep the word always visible; assert with `Palette.decorative=False` |
| Parity | The Desktop pane has the same defect; share `state_badge`/label-column helpers rather than forking a second style |

### 6.7 Impact analysis (AGENTS.md step 8)

**Files to touch in phase 2**

- `presentation/tui/pages/virtual_machines/components/details.py` — new pure builders, panel
  palette injection, optional scroll wrapper.
- `presentation/tui/pages/virtual_machines/selection.py` — replace string assembly with the
  builder; drop `_detail_base`; render loading/failure states.
- `presentation/tui/pages/virtual_machines/page.py` — compose the scroll wrapper.
- `presentation/tui/app.py` — call the builder on mount/empty states; set the panel border title;
  `_set_width_class` is already available if the responsive rule needs a CSS class.
- `presentation/tui/session.py` — reset path renders the placeholder builder (keep text contract).
- `presentation/theme.py` — `state_colour()` extraction + `state_badge()`.
- `presentation/tui/styles.py` — height/scroll/title CSS.
- Optional parity: `virtual_desktops/{components/details.py,controller.py}`.

**Contracts that must not change**

- Widget ids `#detail-box`, `#audit-panel` (documented as a de-facto contract in
  `docs/brain/contracts/MODULE_CONTRACTS.md` §7).
- `markup=False` everywhere; no Textual markup introduced.
- Redaction on every user-visible PVM string; `—`/`N/A` for missing values; object state vs process
  evidence remain distinct (do not merge them into one "running" badge).
- No new PVM reads on highlight/search; Enter keeps the explicit detail read.

**Tests to add/update**

- Plain-text assertions (UUID, name, "No matching VMs", `[REDACTED]`) keep passing.
- New: `Text` spans for `stopped`/`started`/`paused` + `NO_COLOR` fallback; conflict row separate
  from the state value; placeholder/loading/failure copy; 80- and 120-column widths; no clipping
  (all fields present in the rendered lines, not just `str(render())`); UUID never truncated.

**Docs to update after implementation:** `docs/brain/codebase/FILE_CATALOG.md` (details.py /
theme.py responsibilities), `docs/brain/codebase/FEATURE_TO_FILE_MAP.md` (VM inventory page),
`docs/TUI_UNSLOP_PLAN.md` (task 6 re-opened as a detail-pane refinement), and this file's status line.

---

## 7. Acceptance criteria for the refactor (next phase)

1. The pane renders a **structured header + aligned key/value body** built from Rich objects; values
   are aligned in a column, not separated by ad-hoc spaces.
2. `Object state` uses the **same classification and colours as the table** (`state_text` /
   `state_colour`), with the state word still legible with colour disabled.
3. `state_disagreed` is a **separate warning line/row**, visually distinct from the state badge.
4. **Nothing is silently clipped**: base and loaded fields are all reachable (scroll or fitting
   layout) at 80×24 and 120×40.
5. Async detail has visible `Reading…` and `failed` states; `except Exception: return` no longer
   results in an unchanged panel.
6. `markup=False` and per-value redaction preserved; missing values remain `—`.
7. Every existing test that reads `#detail-box` still passes (or is deliberately migrated with a
   documented helper), plus the new span/width/no-clip tests.
8. No new PVM calls caused by cursor movement or typing.

---

## 8. Open questions for the product owner — resolved in §9

1. **State badge glyph:** implemented as `● <state>` with the state word always visible.
2. **Memory formatting:** implemented as grouped megabytes (`8 192 MB`) from `mem_mb`; no unit
   conversion, so nothing is claimed beyond the model.
3. **Failed detail reads:** implemented as `Detail read failed · press Enter to retry`; the raw
   error is not echoed into the pane.
4. **Desktop parity:** deliberately deferred to a follow-up change; the VM pane now owns the
   pattern that the Desktop pane should adopt.

---

## 9. Implementation record

| Area | Change |
|---|---|
| `presentation/theme.py` | `state_colour()` extracted as the single state classification; `status_badge()` and `state_badge()` added; `state_text()` delegates to `state_colour()` and is unchanged for existing callers |
| `pages/virtual_machines/components/details.py` | new pure `build_vm_detail(record, detail, palette)` and `build_detail_placeholder(kind, palette)`; `VMDetailPanel` keeps `id="detail-box"` and `markup=False` |
| `pages/virtual_machines/selection.py` | the pane now renders the builder; `_detail_base` is gone. New state is `_detail_record` / `_detail_loaded` / `_detail_uuid` / `_detail_status`; Enter paints `loading`, a failed read paints `error`, a provider answer for another UUID is rejected |
| `pages/virtual_machines/page.py` | `#detail-box` lives in `VerticalScroll(id="detail-scroll")` |
| `presentation/tui/styles.py` | fixed height/padding replaced by `#detail-scroll { height: auto; max-height: 12; padding: 0 1 }` + `#detail-box { height: auto; min-height: 9 }`; a short record keeps its space, a long description scrolls instead of clipping |
| `presentation/tui/app.py` | detail read-model initialised with the app; border title `Selected VM` uses `group_title("vms", …)` |
| `presentation/tui/session.py` | logout resets the read-model and repaints the `empty` placeholder |
| tests | `tests/unit/test_vm_detail_panel.py` (11 new tests) plus `tests/unit/tui_plain.py`, a type-aware plain-text projection used by the existing `str(render())` assertions |

Rendered result at 80×40 (SVG export, truecolor): labels muted `#a5a5ba`, values foreground
`#e0e0e0`, quantities accent `#87d7d7`, `● started` in `#d7ffd7`, VM name and border title in the
`vms` gradient `#ff87d7`→`#ffafff`, UUID complete on its own row, and no row clipped.

Verification: `ruff check .` clean; `pytest tests/unit` = **351 passed** (340 pre-existing + 11 new).
Environment: Python 3.11.2 with Textual 8.2.8, because this sandbox has no Python 3.12 interpreter;
the repository keeps 3.11 verification possible (`domain/models/snapshots.py` notes it) and no
3.12-only API is used by the change. `pyright` was not run (its Node download is outside the
sandbox's network allowlist).
