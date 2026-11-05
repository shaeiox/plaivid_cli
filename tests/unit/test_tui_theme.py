"""Presentation-only checks for the Gemini-inspired Plaivid theme."""

from __future__ import annotations

import asyncio

from test_cli_and_tui import runtime
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Input,
    Select,
    Static,
    TabbedContent,
)

from plaivid_cli.domain.models import ObjectVM
from plaivid_cli.presentation.theme import (
    ACCENT,
    ANSI16,
    ANSI256,
    BACKGROUND,
    ERROR,
    NO_COLOR,
    PRIMARY,
    SECONDARY,
    SUCCESS,
    TRUECOLOR,
    WARNING,
    brand,
    palette_for,
    styled_metric,
)
from plaivid_cli.presentation.tui.app import PlaividTui


def test_brand_uses_one_accent_without_decorative_gradient():
    wordmark = brand()
    assert "PLAIVID" in wordmark.plain and "PVM console" in wordmark.plain
    styles = {str(span.style) for span in wordmark.spans}
    assert str(wordmark.style) == f"bold {PRIMARY}"
    assert styles == {"#a5a5ba"}  # only the subtitle overrides the accent
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
                assert tui.query_one("#overview-toolbar").region.height == 3
                assert tui.query_one("#interval-apply", Button).region.height == 1
                assert tui.query_one("#overview-refresh", Button).region.height == 1
                assert tui.query_one(Footer).region.height == 1
                field = tui.query_one("#interval-input", Input)
                field.focus()
                await pilot.press("2")
                assert tui.query_one("#tabs", TabbedContent).active == "overview"
                tui.set_focus(None)
                tui.action_vms_page()
                await pilot.pause(.1)
                assert tui.query_one("#tabs", TabbedContent).active == "fleet"
                from rich.text import Text as RichText

                assert "VM list" in RichText.from_markup(str(tui.query_one("#vm-list").border_title)).plain
                assert tui.query_one("#fleet-summary").region.height == 5
                assert tui.query_one("#vm-toolbar").region.height == 3
                for selector, widget in (
                    ("#refresh-button", Button), ("#audit-toggle", Button),
                    ("#bulk-actions", Select), ("#select-all", Checkbox),
                    ("#vm-search", Input),
                ):
                    assert tui.query_one(selector, widget).region.height == 1
                assert tui.query_one("#refresh-button", Button).styles.background.hex.lower() == tui._palette.panel
                table = tui.query_one("#fleet-table", DataTable)
                assert "UUID" not in [column.label.plain for column in table.columns.values()]
                assert table.virtual_size.width <= table.region.width
                assert "UUID" in str(tui.query_one("#detail-box", Static).render())
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
    assert palette_for("truecolor", no_color=True) is NO_COLOR
    assert Color.parse(TRUECOLOR.surface).downgrade(ColorSystem.EIGHT_BIT).number == 17
    for layer in (ANSI256.background, ANSI256.panel, ANSI256.surface):
        assert Color.parse(layer).downgrade(ColorSystem.EIGHT_BIT).number == 233
    assert ANSI256.background == ANSI256.panel == ANSI256.surface


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
                if system == "256":
                    for selector in ("#host-identity", "#running-card", "#cpu-chart", "#nic-detail"):
                        assert tui.query_one(selector).styles.background.hex.lower() == palette.background
                    assert tui.query_one("#fleet-table").styles.background.hex.lower() == palette.background
                    assert tui.query_one(".metric-card").styles.background.hex.lower() == palette.background
                assert tui.query_one("#tabs", TabbedContent).active == "overview"
                assert "Usage" in str(tui.query_one("#cpu-card", Static).render())
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
        assert tui._palette is NO_COLOR
        assert "#000000" in tui.CSS
    finally:
        collection.close()


def test_long_vm_name_keeps_table_readable_at_80_columns(tmp_path, monkeypatch):
    monkeypatch.setenv("COLORTERM", "truecolor")

    async def exercise() -> None:
        provider, collection, application, operations, sessions, _ = runtime(tmp_path)
        original = provider.objects[0]
        provider.objects = (
            ObjectVM(original.uuid, "Eleven-Cluster-ReverseProxy", state="started", vcpu=4, mem_mb=8192),
        )
        tui = PlaividTui(application, operations, sessions)
        try:
            async with tui.run_test(size=(80, 40)) as pilot:
                await pilot.pause(.3)
                tui.action_vms_page()
                await pilot.pause(.1)
                table = tui.query_one("#fleet-table", DataTable)
                assert table.virtual_size.width <= table.region.width
                detail = str(tui.query_one("#detail-box", Static).render())
                assert "Eleven-Cluster-ReverseProxy" in detail
                assert original.uuid in detail
        finally:
            collection.close()

    asyncio.run(exercise())


def test_search_focus_and_live_resize_preserve_keyboard_access(tmp_path, monkeypatch):
    monkeypatch.setenv("COLORTERM", "truecolor")

    async def exercise() -> None:
        _, collection, application, operations, sessions, _ = runtime(tmp_path)
        tui = PlaividTui(application, operations, sessions)
        try:
            async with tui.run_test(size=(80, 40)) as pilot:
                await pilot.pause(.2)
                assert not tui.query_one("#shell").has_class("wide")
                tui.action_vms_page()
                await pilot.pause(.05)
                search = tui.query_one("#vm-search", Input)
                search.focus()
                await pilot.press("q")  # Text entry must not trigger the global quit binding.
                assert tui.is_running and search.value == "q"
                assert tui.focused is search
                assert search.region.height == 1
                assert search.region.width > 0
                await pilot.resize_terminal(120, 40)
                await pilot.pause(.05)
                assert tui.query_one("#shell").has_class("wide")
                assert search.region.width > 0
                tui.set_focus(None)
                await pilot.press("1")
                assert tui.query_one("#tabs", TabbedContent).active == "overview"
                await pilot.resize_terminal(80, 40)
                await pilot.pause(.05)
                assert not tui.query_one("#shell").has_class("wide")
        finally:
            collection.close()

    asyncio.run(exercise())


def test_object_and_cluster_states_are_colored_by_meaning():
    from plaivid_cli.presentation.theme import TRUECOLOR, state_text

    palette = TRUECOLOR
    expected = {
        "started": palette.success, "Running": palette.success,
        "stopped": palette.error, "failed": palette.error,
        "paused": palette.warning, "starting": palette.warning,
        "unknown": palette.muted, "N/A": palette.muted,
    }
    for value, color in expected.items():
        text = state_text(value, palette)
        assert text.plain == value
        assert text.style == f"bold {color}", value
