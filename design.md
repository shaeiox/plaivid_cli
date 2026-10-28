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
layout primitives, (3) metric cards and responsive content/footer grids,
(4) wire interactive draw only, (5) renderer tests, compile and smoke checks,
(6) bump package version. Existing action and monitoring logic remains intact.
