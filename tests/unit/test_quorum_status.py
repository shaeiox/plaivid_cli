from datetime import UTC, datetime

from plaivid_cli.domain.models import CollectionStatus, HostStatus, SectionSnapshot
from plaivid_cli.presentation.logo import LOGO_COLOR, logo_text
from plaivid_cli.presentation.theme import ALARM, TRUECOLOR
from plaivid_cli.tui import _host_status_text, _quorum_verdict

GOOD = HostStatus(name="node-a", ip="192.0.2.10/28", sball_state="quorate", node_state="up", version="7.2.16")


def section(value, last_good, status):
    return SectionSnapshot("host_status", value, last_good, status, datetime.now(UTC), None, 1)


def test_current_quorate_is_ok_and_green():
    level, banner, colour = _quorum_verdict(section(GOOD, GOOD, CollectionStatus.CURRENT), TRUECOLOR)
    assert (level, banner, colour) == ("ok", "SBALL QUORATE", TRUECOLOR.success)


def test_current_non_quorate_is_red_and_names_the_state():
    lost = HostStatus(name="node-a", sball_state="no quorum", node_state="up")
    level, banner, colour = _quorum_verdict(section(lost, None, CollectionStatus.CURRENT), TRUECOLOR)
    assert level == "bad" and colour == ALARM
    assert banner == "SBALL NOT QUORATE · no quorum"


def test_failed_read_is_red_and_never_keeps_last_good_quorate_green():
    # sballd / PVM down: the latest read failed, the store still holds the last good value.
    level, banner, colour = _quorum_verdict(section(None, GOOD, CollectionStatus.UNAVAILABLE), TRUECOLOR)
    assert level == "bad" and colour == ALARM
    assert banner == "SBALL NOT VERIFIED · unavailable"
    text = _host_status_text(GOOD, section(None, GOOD, CollectionStatus.UNAVAILABLE), TRUECOLOR)
    assert "(last known)" in text.plain
    assert all(TRUECOLOR.success not in str(span.style) for span in text.spans)


def test_quorate_but_partial_is_a_warning_not_green():
    level, _, colour = _quorum_verdict(section(GOOD, GOOD, CollectionStatus.PARTIAL), TRUECOLOR)
    assert (level, colour) == ("warn", TRUECOLOR.warning)


def test_missing_section_is_not_verified():
    assert _quorum_verdict(None, TRUECOLOR)[0] == "bad"


def test_logo_colour_follows_the_verdict():
    assert logo_text().style == f"bold {LOGO_COLOR}"
    assert logo_text(ALARM).style == f"bold {ALARM}"
