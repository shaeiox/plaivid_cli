"""Presentation-only checks for the Gemini-inspired Plaivid theme."""

from __future__ import annotations

import asyncio

from test_cli_and_tui import runtime
from textual.widgets import Button, Footer, Input, Static, TabbedContent

from plaivid_cli.presentation.theme import (
    ACCENT,
    ANSI16,
    ANSI256,
    BACKGROUND,
    ERROR,
    PRIMARY,
    SECONDARY,
    SUCCESS,
    TRUECOLOR,
    WARNING,
    brand,
    palette_for,
    styled_metric,
)
from plaivid_cli.tui import PlaividTui


def test_brand_uses_static_blue_purple_rose_gradient_without_changing_text():
    wordmark = brand()
    assert "PLAIVID" in wordmark.plain and "PVM MONITOR" in wordmark.plain
    styles = {str(span.style) for span in wordmark.spans}
    assert str(wordmark.style) == f"bold {PRIMARY}"
    assert len(styles) >= 8  # each brand character has its own color
    assert not any("blink" in style for style in styles)


def test_semantic_metric_text_keeps_status_words_and_units():
    metric = styled_metric("HOST CPU\n19.5%\nONLINE · 0s ago")
    assert metric.plain == "HOST CPU\n19.5%\nONLINE · 0s ago"
    assert f"bold {ACCENT}" in {str(span.style) for span in metric.spans}
    for status, color in (("WARNING", WARNING), ("OFFLINE", ERROR), ("ONLINE", SUCCESS)):
        spans = styled_metric(f"HEARTBEAT\n{status}").spans
        assert f"bold {color}" in {str(span.style) for span in spans}


def test_both_pages_use_custom_theme_and_visible_controls_at_80_and_120(tmp_path, monkeypatch):
    monkeypatch.setenv("COLORTERM", "truecolor")
    async def exercise(width: int) -> None:
        provider, collection, application, operations, sessions, _ = runtime(tmp_path / str(width))
        tui = PlaividTui(application, operations, sessions)
        try:
            async with tui.run_test(size=(width, 40)) as pilot:
                await pilot.pause(.25)
                assert tui.theme == "plaivid-prism"
                assert tui.current_theme.background == BACKGROUND
                assert tui.current_theme.secondary == SECONDARY
                assert tui.query_one("#tabs", TabbedContent).active == "overview"
                assert "PLAIVID" in str(tui.query_one("#brand", Static).render())
                assert "Apply" in str(tui.query_one("#interval-apply", Button).render())
                assert "Refresh" in str(tui.query_one("#overview-refresh", Button).render())
                assert "Refresh: 3s" in str(tui.query_one("#refresh-label", Static).render())
                assert tui.query_one(Footer).region.height == 1
                # The live panel shows real collection status, not an animated fake heartbeat.
                assert "HOST HEARTBEAT" in str(tui.query_one("#heartbeat-card", Static).render())
                field = tui.query_one("#interval-input", Input)
                field.focus()
                await pilot.press("2")
                assert tui.query_one("#tabs", TabbedContent).active == "overview"
                tui.action_vms_page()
                assert tui.query_one("#tabs", TabbedContent).active == "fleet"
                assert "VM LIST" in str(tui.query_one("#vm-list").border_title)
        finally:
            collection.close()

    for width in (80, 120):
        asyncio.run(exercise(width))


def test_terminal_palettes_do_not_quantize_dark_surfaces_to_navy():
    from rich.color import Color, ColorSystem

    assert palette_for("truecolor") is TRUECOLOR
    assert palette_for("256") is ANSI256
    assert palette_for("standard") is ANSI16
    assert palette_for(None) is ANSI16
    assert palette_for("truecolor", no_color=True) is ANSI16
    assert Color.parse(TRUECOLOR.surface).downgrade(ColorSystem.EIGHT_BIT).number == 17
    assert Color.parse(ANSI256.surface).downgrade(ColorSystem.EIGHT_BIT).number == 235
    assert Color.parse(ANSI256.panel).downgrade(ColorSystem.EIGHT_BIT).number == 234
    assert Color.parse(ANSI256.background).downgrade(ColorSystem.EIGHT_BIT).number == 233


def test_256_and_standard_terminal_render_with_matching_widget_and_control_theme(tmp_path, monkeypatch):
    async def exercise(system: str, palette) -> None:
        _, collection, application, operations, sessions, _ = runtime(tmp_path / system)
        tui = PlaividTui(application, operations, sessions)
        try:
            assert tui.console.color_system == system
            assert tui._palette is palette
            async with tui.run_test(size=(120, 40)) as pilot:
                await pilot.pause(.2)
                assert tui.current_theme.background == palette.background
                assert tui.current_theme.surface == palette.surface
                assert tui.query_one("#cpu-card", Static).styles.background.hex.lower() == palette.surface
                assert tui.query_one("#topbar").styles.background.hex.lower() == palette.panel
                assert tui.query_one("#overview-toolbar").styles.background.hex.lower() == palette.panel
                assert tui.query_one("#tabs", TabbedContent).active == "overview"
                assert "HOST CPU" in str(tui.query_one("#cpu-card", Static).render())
        finally:
            collection.close()

    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("COLORTERM", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    asyncio.run(exercise("256", ANSI256))
    monkeypatch.setenv("TERM", "xterm")
    asyncio.run(exercise("standard", ANSI16))


def test_no_color_takes_precedence_even_when_truecolor_is_advertised(tmp_path, monkeypatch):
    monkeypatch.setenv("COLORTERM", "truecolor")
    monkeypatch.setenv("NO_COLOR", "")  # Presence, even if empty, disables color in Textual.
    _, collection, application, operations, sessions, _ = runtime(tmp_path / "mono")
    try:
        tui = PlaividTui(application, operations, sessions)
        assert tui.console.color_system == "truecolor"
        assert tui._palette is ANSI16
        assert "#000000" in tui.CSS
    finally:
        collection.close()
