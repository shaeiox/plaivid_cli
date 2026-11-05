from datetime import UTC, datetime

from plaivid_cli.domain.models import CollectionStatus, HostStatus, SectionSnapshot
from plaivid_cli.presentation.logo import LOGO_COLOR, logo_text
from plaivid_cli.presentation.theme import ALARM, CAUTION, TRUECOLOR
from plaivid_cli.presentation.tui import _host_status_text, _quorum_verdict

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
    assert (level, colour) == ("warn", CAUTION)


def test_missing_section_is_not_verified():
    assert _quorum_verdict(None, TRUECOLOR)[0] == "bad"


def test_logo_colour_follows_the_verdict():
    assert logo_text().style == f"bold {LOGO_COLOR}"
    assert logo_text(ALARM).style == f"bold {ALARM}"


def test_failed_read_with_missing_pid_file_is_not_operational():
    failed = section(None, GOOD, CollectionStatus.UNAVAILABLE)
    level, banner, colour = _quorum_verdict(failed, TRUECOLOR, pid_file=False)
    assert (level, colour) == ("bad", ALARM)
    assert banner == "SBALL NOT OPERATIONAL · PID file missing, sbell not responding"


def test_failed_read_with_pid_file_present_stays_not_verified():
    failed = section(None, GOOD, CollectionStatus.UNAVAILABLE)
    assert _quorum_verdict(failed, TRUECOLOR, pid_file=True)[1] == "SBALL NOT VERIFIED · unavailable"
    assert _quorum_verdict(failed, TRUECOLOR, pid_file=None)[1] == "SBALL NOT VERIFIED · unavailable"


def test_pid_file_check_reports_missing_present_and_unknown(tmp_path, monkeypatch):
    from pathlib import Path

    from plaivid_cli.infrastructure.local_monitor import sballd_pid_file_present

    missing = tmp_path / "sballd.pid"
    assert sballd_pid_file_present(missing) is False
    missing.write_text("1234\n")
    assert sballd_pid_file_present(missing) is True

    def denied(self):
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "exists", denied)
    assert sballd_pid_file_present(missing) is None


def test_quorating_is_yellow_not_red():
    forming = HostStatus(name="spongebob", sball_state="quorating", node_state="up")
    level, banner, colour = _quorum_verdict(section(forming, None, CollectionStatus.CURRENT), TRUECOLOR)
    assert (level, colour) == ("warn", CAUTION)
    assert banner == "SBALL QUORATING"


def test_quorating_with_partial_read_says_so():
    forming = HostStatus(name="spongebob", sball_state="quorating", node_state="up")
    banner = _quorum_verdict(section(forming, None, CollectionStatus.PARTIAL), TRUECOLOR)[1]
    assert banner == "SBALL QUORATING · partial"


def test_failed_read_during_quorating_is_still_red():
    # A failed read is never shown as a forming cluster.
    level, _, colour = _quorum_verdict(section(None, None, CollectionStatus.UNAVAILABLE), TRUECOLOR)
    assert (level, colour) == ("bad", ALARM)
