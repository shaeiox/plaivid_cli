# ADR 0001 — Strict 60-second wall-clock chart window and dynamic Y scale

- **Status:** Implementation-observed, documented 2026-11-08. **Not a recorded owner decision.**
- **Date:** Documented 2026-11-08; source change is commit `89fe3d0` (2026-11-08,
  "Refactor dashboard card layout and chart rendering"). The current local date is 2026-11-08.
- **Decision owner:** none recorded. This ADR describes code, not an approval.
- **Evidence:** `plaivid_cli/application/overview.py::OverviewHistory`,
  `plaivid_cli/presentation/tui/refresh.py::RefreshMixin`,
  `plaivid_cli/presentation/tui/pages/overview/controller.py::OverviewMixin`,
  `plaivid_cli/presentation/charts/render.py::dynamic_top`,
  `tests/unit/test_graph_history.py`, `tests/unit/test_dashboard_chart_refactor.py`,
  `docs/MONITORING_DASHBOARD.md`.

## Context

The Overview CPU and Load charts show a rolling 60-second window. A chart that scales only on
new samples retains a stale high peak when collection stalls, and a chart that prunes only on
sample arrival never advances its time axis. Background grid dots merged into data cells also
produced data-colored artifacts, and two-dot Braille thickening reduced resolution.

## Decision (as implemented)

1. `OverviewHistory.prune(now=None)` defaults to `time.monotonic()` and drops samples older
   than `now − 60 s`; `RefreshMixin._tick` calls it on every timer tick, independently of
   collection success.
2. `_render_charts(*, now=None)` computes a `t_end` from an explicit UI clock (or, for direct
   calls, a fixture-clock fallback) and uses it consistently for pruning, window selection,
   `dynamic_top`, and both `set_chart()` calls.
3. `dynamic_top` derives the Y ceiling from `window_peak()` over **only visible samples** plus
   `SCALE_HEADROOM` (1.15), snapped to a round step, with no hysteresis — a peak leaving the
   window shrinks the scale immediately. The legacy `stable_top` retains a
   `strict=False` hysteresis path for existing tests.
4. Grid dots are a separate `GRID_STYLE = "dim #3f3f4e"` layer and are never OR-ed into data
   glyphs; Braille lines are one dot thick; the axis is a smooth `─`/`┴` rule with
   `-60s`, `-30s`, `now`; a left gutter shows dynamic Y-Max/Y-Mid/0.
5. Chart redraw is throttled to ~1 Hz (or immediate when pruning dropped a peak) and guarded
   against teardown (`NoMatches`, mounted-chart queries).

## Alternatives (as evidenced by retained code)

- **`stable_top` hysteresis:** keep the previous ceiling until it is much larger than needed.
  Retained for compatibility/tests but not used for the dashboard's strict path.
- **Sample-count-based pruning:** prune only when a new sample arrives. Rejected by the
  implementation because the window must advance during a collection stall.
- **Two-dot Braille thickening / merged grid layer:** former behavior, removed in commit
  `89fe3d0`; no runtime path now thickens Braille lines.

## Consequences

- Charts stay truthful during stalls: the visible time window always represents the last 60 s
  of wall-clock time, and a departed peak no longer squashes low activity.
- Direct controller calls with synthetic/fixture timestamps anchor to the newest sample when
  they differ from the wall clock by more than the window; explicit UI ticks still enforce real
  wall-clock pruning.
- `ChartView` must tolerate `palette` and extra composition keywords (added in the same
  change) because cards pass them at mount time.
- Regression coverage is required for card order, header status, wall-clock pruning, strict
  shrink, Y labels, grid styling, Braille sharpness, axis glyphs, and widget kwargs
  (`tests/unit/test_dashboard_chart_refactor.py`).

## Related modules

`plaivid_cli/application/overview.py`, `plaivid_cli/presentation/charts/`,
`plaivid_cli/presentation/tui/pages/overview/`, `plaivid_cli/presentation/tui/refresh.py`,
`docs/MONITORING_DASHBOARD.md`, [`../../codebase/FEATURE_TO_FILE_MAP.md`](../../codebase/FEATURE_TO_FILE_MAP.md).
