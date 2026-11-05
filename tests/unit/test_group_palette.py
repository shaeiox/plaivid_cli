import colorsys

from plaivid_cli.presentation.theme import (
    GROUP_STOPS,
    NO_COLOR,
    TRUECOLOR,
    gradient_text,
    group_color,
    group_title,
)


def _hue(hex_colour: str) -> float:
    r, g, b = (int(hex_colour.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, _, _ = colorsys.rgb_to_hls(r, g, b)
    return h * 360


def test_group_hues_stay_out_of_alarm_warning_and_ok_bands() -> None:
    # Red (around 0 deg), yellow (around 60 deg) and green (around 120 deg) are reserved for status.
    reserved = ((-12, 12), (50, 70), (100, 150))
    for group, stops in GROUP_STOPS.items():
        for colour in stops:
            hue = _hue(colour) % 360
            assert not any(low <= hue <= high or low <= hue - 360 <= high for low, high in reserved), (group, colour)


def test_gradient_runs_from_start_to_end_colour() -> None:
    text = gradient_text("abcd", "#000000", "#ffffff")
    colours = [str(span.style) for span in text.spans]
    assert colours[0].endswith("#000000") and colours[-1].endswith("#ffffff")
    assert len({c for c in colours}) == 4


def test_no_color_and_16_colour_output_get_no_gradient_or_border_colour() -> None:
    assert group_color("host", NO_COLOR) is None
    assert group_color("host", TRUECOLOR) == GROUP_STOPS["host"][0]
    plain = group_title("io", "Storage", NO_COLOR)
    assert plain.plain == "Storage"
    assert plain.spans == []
