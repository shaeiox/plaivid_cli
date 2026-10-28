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
The previous line editor waited only 40 ms for the tail of an Escape sequence
and recognized a few fixed CSI values. Terminals can split escape bytes across
reads or use SS3 sequences (for example `ESC O A`); after the short timeout,
the remaining printable bytes such as `[6~` or `OA` were appended to the
command buffer. Page keys therefore appeared as text instead of scrolling.

### Architecture
- The interactive terminal reader is the single input boundary. It consumes
  complete CSI/SS3 sequences and maps them to semantic page/history events;
  unknown escape sequences are consumed, never inserted into commands.
- The renderer receives a compact-layout flag derived from terminal height.
  On compact screens it prioritizes metric cards and inventory, hides the
  contextual rail, and condenses command/legend help. Wide/tall terminals keep
  the full dashboard.
- Page scrolling is a viewport operation only when the rendered screen is
  taller than the terminal. This avoids paging through help/rail content on
  ordinary terminals while preserving all inventory rows for small screens.

### Implemented tasks
1. Decode complete CSI/SS3 terminal sequences with per-byte timeout tolerance.
2. Map Page Up/Down to page-sized viewport movement; keep arrow history keys.
3. Use a height-aware compact layout and vertically stack boxes at narrow widths.
4. Add regression tests for escape-byte consumption, compact layout, and paging.
