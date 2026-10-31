"""Presentation-only checks for the Gemini-inspired Plaivid theme."""

from __future__ import annotations

import asyncio

from test_cli_and_tui import runtime
from textual.widgets import Button, Footer, Input, Static, TabbedContent

from plaivid_cli.presentation.theme import (
    ACCENT,
    BACKGROUND,
    ERROR,
    PRIMARY,
    SECONDARY,
    SUCCESS,
    WARNING,
    brand,
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


def test_both_pages_use_custom_theme_and_visible_controls_at_80_and_120(tmp_path):
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
