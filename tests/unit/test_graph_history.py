from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from plaivid_cli.application.overview import OverviewHistory
from plaivid_cli.domain.models import ApplicationSnapshot, CollectionStatus, SectionSnapshot
from plaivid_cli.domain.overview import LocalHostSample
from plaivid_cli.infrastructure.local_monitor import LinuxMonitor
from plaivid_cli.presentation.charts import bucketed

KEYS = ("cpu", "memory", "load", "load5", "load15")


def _snapshot(generation: int, stamp: float, cpu: float = 10.0, load1: float = 1.0,
              status: CollectionStatus = CollectionStatus.CURRENT) -> ApplicationSnapshot:
    sample = LocalHostSample(cpu_percent=cpu, memory_used=500, memory_total=1000,
                             load1=load1, load5=load1 + 10, load15=load1 + 20)
    now = datetime.now(UTC)
    section = SectionSnapshot("local_host", sample, sample, status, now, now, generation,
                              succeeded_monotonic=stamp)
    return ApplicationSnapshot(generation, now, (section,))


def _state(history: OverviewHistory) -> dict[str, list[tuple[float, float]]]:
    return {key: list(history.values[key]) for key in KEYS}


def test_no_new_sample_leaves_history_unchanged() -> None:
    history = OverviewHistory()
    history.add(_snapshot(1, 0.0))
    before = _state(history)
    history.add(_snapshot(1, 0.0))  # same generation: a repeated publish
    history.add(_snapshot(2, 3.0, status=CollectionStatus.STALE))  # stale read is not a sample
    assert _state(history) == before


def test_each_refresh_appends_exactly_one_sample_and_keeps_order() -> None:
    history = OverviewHistory()
    for index in range(10):
        before = _state(history)
        history.add(_snapshot(index + 1, float(index * 3), cpu=float(index)))
        after = _state(history)
        for key in KEYS:
            assert len(after[key]) == len(before[key]) + 1
            assert after[key][:-1] == before[key]  # earlier samples keep their values and places
    stamps = [stamp for stamp, _ in history.values["cpu"]]
    assert stamps == sorted(stamps)
    assert [value for _, value in history.values["cpu"]] == [float(i) for i in range(10)]


def test_consecutive_refreshes_do_not_reset_the_history_object() -> None:
    history = OverviewHistory()
    series = history.values["cpu"]
    for index in range(5):
        history.add(_snapshot(index + 1, float(index)))
    assert history.values["cpu"] is series
    assert len(series) == 5


def test_rolling_buffer_drops_only_the_oldest_sample() -> None:
    history = OverviewHistory(limit=5)
    for index in range(8):
        history.add(_snapshot(index + 1, float(index), cpu=float(index)))
    values = [value for _, value in history.values["cpu"]]
    assert values == [3.0, 4.0, 5.0, 6.0, 7.0]


def test_load_graph_uses_the_first_value_of_proc_loadavg(tmp_path: Path) -> None:
    (tmp_path / "stat").write_text("cpu  20 0 10 70 0 0 0\n")
    (tmp_path / "meminfo").write_text("MemTotal: 1000 kB\nMemAvailable: 250 kB\n")
    (tmp_path / "loadavg").write_text("0.11 0.22 0.33 1/100 42\n")
    (tmp_path / "uptime").write_text("120.5 80.2\n")
    monitor = LinuxMonitor(tmp_path, tmp_path / "no-net")
    sample = monitor.host()
    assert sample.load1 == 0.11 and sample.load5 == 0.22 and sample.load15 == 0.33

    history = OverviewHistory()
    history.add(ApplicationSnapshot(1, datetime.now(UTC), (SectionSnapshot(
        "local_host", sample, sample, CollectionStatus.CURRENT, None, None, 1, succeeded_monotonic=0.0),)))
    assert history.values["load"][-1][1] == 0.11  # the 1-minute average
    assert history.values["load5"][-1][1] == 0.22
    assert history.values["load15"][-1][1] == 0.33
    assert history.values["load"][-1][1] not in (0.22, 0.33)


def test_completed_buckets_do_not_change_when_new_samples_arrive() -> None:
    samples = [(float(t), float((t * 7) % 23)) for t in range(0, 50)]
    before = bucketed(tuple(samples), 0.0, 50.0, 2.0)
    later = samples + [(50.0, 4.0), (51.0, 9.0)]
    after = bucketed(tuple(later), 0.0, 52.0, 2.0)
    completed = [point for point in before if point[0] < 49.0]  # buckets that no new sample touches
    assert len(completed) > 20
    assert [point for point in after if point[0] < 49.0] == completed


def test_repeated_refreshes_of_the_same_data_give_the_same_points() -> None:
    samples = tuple((float(t), float(t % 5)) for t in range(0, 60))
    first = bucketed(samples, 0.0, 59.0, 2.0)
    second = bucketed(samples, 0.0, 59.0, 2.0)
    assert first == second
