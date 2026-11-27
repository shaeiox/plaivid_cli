"""Overview scheduling, bounded history and collection-backed health (no I/O)."""

from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass

from plaivid_cli.domain.models import ApplicationSnapshot, CollectionStatus, SectionSnapshot


@dataclass(frozen=True, slots=True)
class Health:
    status: str
    age: float | None
    last_success: str | None
    latency: float | None
    detail: str


def health(section: SectionSnapshot[object] | None, cadence: float, *, now: float | None = None) -> Health:
    clock = time.monotonic() if now is None else now
    if section is None:
        return Health("LOADING", None, None, None, "Awaiting first sample")
    if section.status is CollectionStatus.UNSUPPORTED:
        return Health("N/A", None, None, None, "Unsupported or unverified source")
    last = section.succeeded_monotonic
    age = max(0.0, clock - last) if last is not None else None
    timeout = max(3 * cadence, 30 + cadence)
    if age is None:
        # Failed first read has no successful heartbeat to display.
        status = "WARNING" if section.attempted_at else "LOADING"
        detail = section.error or "Awaiting first valid response"
    elif age > timeout:
        status, detail = "OFFLINE", "No recent successful monitoring response"
    elif age > 2 * cadence or section.status not in (CollectionStatus.CURRENT, CollectionStatus.PARTIAL):
        status, detail = "WARNING", section.error or "Monitoring data is stale"
    elif section.status is CollectionStatus.PARTIAL:
        status, detail = "WARNING", "Partial monitoring response"
    else:
        status, detail = "ONLINE", "Latest response valid"
    if age is None and section.attempted_monotonic is not None and clock - section.attempted_monotonic > timeout:
        status = "OFFLINE"
    return Health(
        status, age, section.succeeded_at.astimezone().strftime("%H:%M:%S") if section.succeeded_at else None,
        section.latency_seconds, detail,
    )


class OverviewSchedule:
    """Single demand controller. The Textual app owns one timer and one worker."""

    def __init__(self, interval: float = 3.0, host_status_interval: float = 2.0) -> None:
        if not math.isfinite(host_status_interval) or host_status_interval <= 0:
            raise ValueError("host_status_interval must be a finite positive number")
        self.host_status_interval = host_status_interval
        self.set_interval(interval)
        self.active = False
        self.busy = False
        self.next_due: dict[str, float] = {}

    def set_interval(self, seconds: float) -> None:
        if not math.isfinite(seconds) or not 1 <= seconds <= 60:
            raise ValueError("Refresh must be a whole number of seconds from 1 to 60")
        self.interval = seconds
        # Reschedule the next lightweight sample without spawning a timer.
        if hasattr(self, "next_due"):
            self.next_due["local"] = time.monotonic() + seconds

    def enter(self) -> None:
        self.active = True
        if not self.next_due:
            self.next_due = {"local": 0, "pvm": 0, "host": 0, "discovery": 0}
        else:
            self.next_due["local"] = 0
            self.next_due["host"] = 0

    def leave(self) -> None:
        self.active = False

    def reset(self) -> None:
        self.leave()
        self.next_due.clear()

    def background_due(self, *, now: float | None = None) -> tuple[str, ...]:
        """Keep the local graph history sampling while another tab is shown.

        Only the local /proc sample runs (no server request), at the same cadence as the Overview.
        """
        if self.active or self.busy:
            return ()
        clock = time.monotonic() if now is None else now
        if clock >= self.next_due.get("local", float("inf")):
            self.next_due["local"] = clock + self.interval
            self.busy = True
            return ("local_host",)
        return ()

    def due(self, *, now: float | None = None) -> tuple[str, ...]:
        if not self.active or self.busy:
            return ()
        clock = time.monotonic() if now is None else now
        sections: list[str] = []
        if clock >= self.next_due.get("discovery", float("inf")):
            sections.append("physical_nics")
            self.next_due.pop("discovery", None)
        if clock >= self.next_due.get("local", float("inf")):
            sections.extend(("local_host", "nic_samples"))
            self.next_due["local"] = clock + self.interval
        if clock >= self.next_due.get("pvm", float("inf")):
            sections.extend(("inventory", "dashboard", "host_metrics"))
            self.next_due["pvm"] = clock + max(18, self.interval)
        # sball show is cheap, so host status keeps its own faster cadence outside the PVM batch.
        if clock >= self.next_due.get("host", float("inf")):
            sections.append("host_status")
            self.next_due["host"] = clock + self.host_status_interval
        if sections:
            self.busy = True
        return tuple(sections)

    def finished(self) -> None:
        self.busy = False

    def rediscover(self) -> None:
        self.next_due["discovery"] = 0


# Length of the Overview graph history. Samples older than this are dropped.
HISTORY_WINDOW_SECONDS = 60.0


def window_points(
    points: Iterable[tuple[float, float]],
    t_end: float,
    window: float = HISTORY_WINDOW_SECONDS,
) -> tuple[tuple[float, float], ...]:
    """Samples still visible in the rolling window ``[t_end - window, t_end]``.

    ``t_end`` is the current wall/monotonic clock, **not** the timestamp of the
    newest sample: during a collection stall the window keeps advancing, so old
    peaks leave it on time instead of pinning the chart scale forever.
    """
    t0 = t_end - window
    return tuple(
        (stamp, value)
        for stamp, value in points
        if math.isfinite(stamp) and math.isfinite(value) and t0 <= stamp <= t_end
    )


class OverviewHistory:
    """Timestamped local samples for the Overview graphs. Missing samples are never stored as zero.

    The 60-second window is anchored to the *clock*, not to the last sample: ``prune``
    can be called on every UI tick so the visible history shrinks even when collection
    stalls. ``add`` keeps its original behaviour when no explicit clock is supplied,
    which lets callers feed synthetic/fixture timestamps in tests.
    """

    def __init__(self, limit: int = 1024) -> None:
        self.values: dict[str, deque[tuple[float, float]]] = {
            name: deque(maxlen=limit) for name in ("cpu", "memory", "load", "load5", "load15")
        }
        self._last_generation: int | None = None
        self.last_verified_running: int | None = None

    def prune(self, now: float | None = None) -> int:
        """Drop samples older than ``now - HISTORY_WINDOW_SECONDS`` from every series.

        ``now`` uses the same monotonic clock as ``SectionSnapshot.succeeded_monotonic``.
        Returns the number of dropped points so callers can tell that the window moved.
        """
        clock = time.monotonic() if now is None else now
        cutoff = clock - HISTORY_WINDOW_SECONDS
        dropped = 0
        for series in self.values.values():
            while series and series[0][0] < cutoff:
                series.popleft()
                dropped += 1
        return dropped

    def window(
        self, name: str, *, now: float | None = None, t_end: float | None = None
    ) -> tuple[tuple[float, float], ...]:
        """Visible points for one series at the current wall-clock window end."""
        end = t_end if t_end is not None else (time.monotonic() if now is None else now)
        return window_points(self.values[name], end)

    def peak(
        self, name: str, *, now: float | None = None, t_end: float | None = None
    ) -> float | None:
        """Highest *active* value in the visible window, or None when there is none."""
        return max((value for _, value in self.window(name, now=now, t_end=t_end)), default=None)

    def add(self, snapshot: ApplicationSnapshot, *, now: float | None = None) -> None:
        """Append one validated sample and prune against the supplied wall clock.

        With ``now=None`` the newest sample's timestamp is used as the clock (the
        legacy, sample-relative behaviour). Pass ``now=time.monotonic()`` to enforce
        wall-clock pruning even when a sample arrives late or collection stalls.
        """
        section = snapshot.section("local_host")
        if section is None or section.generation == self._last_generation or section.status is not CollectionStatus.CURRENT:
            return
        from plaivid_cli.domain.overview import LocalHostSample

        sample = section.value
        if not isinstance(sample, LocalHostSample) or section.succeeded_monotonic is None:
            return
        self._last_generation = section.generation
        metrics = {
            "cpu": sample.cpu_percent,
            "memory": 100 * sample.memory_used / sample.memory_total if sample.memory_used is not None and sample.memory_total else None,
            "load": sample.load1,
            "load5": sample.load5,
            "load15": sample.load15,
        }
        stamp = section.succeeded_monotonic
        clock = stamp if now is None else now
        self.prune(clock)
        for key, value in metrics.items():
            if value is not None and math.isfinite(value):
                self.values[key].append((stamp, value))
        # A late/stalled sample that is itself outside the window must not be kept.
        self.prune(clock)


def sparkline(values: deque[tuple[float, float]], width: int = 32) -> str:
    """Exactly ``width`` cells: samples are linearly resampled so the line spans the whole card."""
    if len(values) < 2:
        return "Waiting for samples"
    marks = "▁▂▃▄▅▆▇█"
    numbers = [value for _, value in values]
    high = max(numbers)
    low = min(numbers)
    width = max(2, width)
    last = len(numbers) - 1
    cells: list[float] = []
    for column in range(width):
        position = column * last / (width - 1)
        left = int(position)
        right = min(left + 1, last)
        fraction = position - left
        cells.append(numbers[left] * (1 - fraction) + numbers[right] * fraction)
    return "".join(marks[min(7, int(7 * (value - low) / (high - low)))] if high > low else marks[0] for value in cells)
