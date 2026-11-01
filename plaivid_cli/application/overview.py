"""Overview scheduling, bounded history and collection-backed health (no I/O)."""

from __future__ import annotations

import math
import time
from collections import deque
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

    def __init__(self, interval: float = 3.0) -> None:
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
            self.next_due = {"local": 0, "pvm": 0, "discovery": 0}
        else:
            self.next_due["local"] = 0

    def leave(self) -> None:
        self.active = False

    def reset(self) -> None:
        self.leave()
        self.next_due.clear()

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
            sections.extend(("inventory", "dashboard", "host_status", "host_metrics"))
            self.next_due["pvm"] = clock + max(18, self.interval)
        if sections:
            self.busy = True
        return tuple(sections)

    def finished(self) -> None:
        self.busy = False

    def rediscover(self) -> None:
        self.next_due["discovery"] = 0


class OverviewHistory:
    def __init__(self, limit: int = 32) -> None:
        self.values: dict[str, deque[tuple[float, float]]] = {
            name: deque(maxlen=limit) for name in ("cpu", "memory", "load")
        }
        self._last_generation: int | None = None
        self.last_verified_running: int | None = None

    def add(self, snapshot: ApplicationSnapshot) -> None:
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
        }
        for key, value in metrics.items():
            if value is not None and math.isfinite(value):
                self.values[key].append((section.succeeded_monotonic, value))


def sparkline(values: deque[tuple[float, float]]) -> str:
    if len(values) < 2:
        return "Waiting for samples"
    marks = "▁▂▃▄▅▆▇█"
    numbers = [value for _, value in values]
    high = max(numbers)
    low = min(numbers)
    return "".join(marks[min(7, int(7 * (value - low) / (high - low)))] if high > low else marks[0] for value in numbers)
