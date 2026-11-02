# Plaivid TUI refinement plan

Method: [Unslop](../.agents/skills/unslop/SKILL.md) by Damir Sokolovsky, CC BY 4.0. This is a terminal interface: adapt the skill's visual heuristics to character cells, Textual focus, and 16/256/truecolor terminals. No browser assets, generated images, motion, dependency or PVM calls are required. This plan tracks the work; it is not evidence of real-PVM acceptance.

## Audit (current screen)

- The static blue→purple→rose wordmark in `presentation/theme.py` makes the header compete with the data; use a solid mark and one accent.
- `tui.py` uses many rounded boxes and accent-colored borders, so hierarchy relies on decoration rather than source freshness. Keep the cards that group genuine metrics, quiet the chrome, and reserve semantic borders for real warning/error states.
- `presentation/overview.py` decorates every metric with unrelated glyphs (`◆`, `◉`, `▣`, `⌁`, `♥`) and all-caps titles. Keep the actual measured values and status, remove decorative glyphs and normalize sentence-case copy.
- Refresh, action and audit controls are repeated with small alignment differences. Use one spacing/width rhythm for both fleet pages.
- Login warning and host provenance need legible secondary copy; warning text cannot depend on color alone.
- The VM list lacks the Desktop list's local search. Filtering must not request PVM per keystroke, alter unfiltered Apply to all, or silently operate on a hidden row.
- Focus, no-color/256-color and 80/120-column layouts need regression checks after CSS and copy changes. No animated or fabricated telemetry should be introduced.

## Direction (from the product)

- **Product:** A local terminal console for operators to observe PVM host health and act on VM/Desktop inventory.
- **Character:** exact, quiet, dependable.
- **World:** a night-shift instrument panel, where readings and provenance—not decorative chrome—lead.
- **Moments:** the observed host-health state and real CPU/memory/load history. If a source is unavailable, N/A remains prominent rather than a made-up graphic.
- **Signature:** one restrained status marker tied to real collection state, alongside a readable text label.

## Small tasks, in order

- [x] 1. Install the complete Unslop skill project-locally at `.agents/skills/unslop/` with its CC BY 4.0 license and attribution. Review its signs and token guidance.
- [x] 2. Audit all three pages plus sign-in and set the five-line direction above; preserve the existing Gemini-inspired terminal palette as a restrained accent rather than inventing a different brand.
- [x] 3. Establish one terminal-cell spacing/control rhythm in shared Textual CSS for sign-in, navigation, Overview and both inventories. Preserve visible focus and compact controls.
- [x] 4. Quiet the wordmark and chrome; use one primary accent, a restrained data-value tint, and semantic warning/error colors, with truecolor, 256-color and no-color fallbacks.
- [x] 5. Normalize Overview headings, metric labels and status copy without changing a collector, field meaning, source budget, or real-state distinctions.
- [x] 6. Align VM/Desktop list summaries, actions, detail, search placement and empty/loading/stale states at 80 and 120 columns.
- [x] 7. Verify keyboard navigation, readable status without color, logout/focus and responsive resizing on all pages with Textual Pilot.
- [x] 8. **Last feature task:** add local name search to the VM page like Virtual Desktops. Preserve full UUID selection, move hidden selection to the first visible match or clear it, leave Apply to all unfiltered, and never read PVM per keystroke.
- [x] 9. Update visual-system documentation, run pytest/Ruff/Pyright/build/diff checks, and report any unverified real-host appearance or behavior.

The user requested implementation to start now; no separate design approval wait is required. Each task is small enough to test before the next one. No automatic action confirmation is reintroduced.

## Verification and limits

Local verification: 146 passing tests including search/UUID/bulk safety, login/logout state, keyboard focus, 80↔120-column resize and 16/256/truecolor/no-color palette tests; Ruff and Pyright clean; package build and `git diff --check` clean. No live PVM operation or on-host visual acceptance was performed. The Desktop action protocol still needs separate authorized validation.

The skill's web-only image, browser typography and animation passes are intentionally inapplicable to this terminal application; the real sample history and collection-state rail are its visual content. No invented data, extra collectors or motion were added.
