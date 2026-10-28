# Dashboard design record

The supplied reference depicts a dense, dark, terminal-first PVM dashboard.
It is organized as: a keyboard-hint header; seven compact host/metric cards;
a dominant VM inventory with a context rail; three command/action/legend
reference panels; and a full-width connection/status footer.

Implementation constraints:
- Keep rendering pure and use the existing `host` and `VM` data already fetched.
- Do not add transport requests or change action/command behavior for appearance.
- Preserve no-color and ASCII fallbacks.
- At narrow widths, collapse side-by-side content into stacked panels rather
  than allowing columns to overlap.
- Do not claim keyboard actions or live network/clock rates unless they are
  actually wired to input/data collection. The current UI is command-line driven;
  rows are displayed in inventory order, not interactively selected.

Incremental implementation plan: (1) design analysis (this file), (2) pure
layout primitives, (3) metric cards and responsive content/footer grids, (4) apply the same
panel language to the live `overview` page while preserving its sampling and
refresh loop, (5) renderer tests, compile and smoke checks, (6) bump package
version. Existing action and monitoring logic remains intact.

## Small-screen paging follow-up

### Root cause
The line editor read through buffered `sys.stdin` while polling the underlying
file descriptor with `select`. `TextIOWrapper` can prefetch the rest of a key
sequence, leaving the fd unreadable to `select`; the handler timed out and then
consumed printable tails such as `[6~` or `OA` as ordinary command text. The
short timeout and limited CSI handling made this worse for split writes and
SS3 keys. Mouse reporting was not enabled, and there was no parser for SGR
wheel reports.

### Architecture
- The interactive terminal reader is the single input boundary. It reads raw
  bytes directly from the terminal fd, consumes complete CSI/SS3 sequences,
  and maps Page Up/Down and wheel events to scrolling; unknown escape and mouse
  sequences are consumed, never inserted into commands.
- SGR mouse reporting is enabled only inside the full-screen session and both
  mouse modes are disabled on every exit path.
- The renderer receives a compact-layout flag derived from terminal height.
  On compact screens it prioritizes metric cards and inventory, hides the
  contextual rail, and condenses command/legend help. Wide/tall terminals keep
  the full dashboard.
- Page scrolling is a viewport operation only when the rendered screen is
  taller than the terminal. This avoids paging through help/rail content on
  ordinary terminals while preserving all inventory rows for small screens.

### Implemented tasks
1. Read terminal input directly from the raw fd and decode CSI/SS3 sequences.
2. Enable/disable SGR mouse reporting and map wheel/Page Up/Down to scrolling.
3. Use a height-aware compact layout and vertically stack boxes at narrow widths.
4. Add regression tests for key/mouse consumption, compact layout, and paging.

## Zoned rendering follow-up

- A fixed screen frame is painted by `TerminalRenderer` with absolute cursor
  addressing, a previous-frame buffer, and row-level diffing. The alternate
  screen is cleared only on first paint or resize.
- The renderer keeps header, metric cards, context rail, and footer at fixed
  rows. `vm_offset`/`vm_limit` window only inventory rows; Page Up/Down and
  wheel events change this window, not the entire dashboard viewport.
- The list window size is computed from terminal geometry and wrapped row
  heights. On resize, the frame is recalculated and repainted; on list scroll,
  unchanged rows are not emitted to the terminal.
