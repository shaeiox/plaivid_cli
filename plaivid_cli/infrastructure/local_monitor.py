"""Bounded local read-only Linux host and physical-interface sampling."""

from __future__ import annotations

import math
import re
import socket
import time
from pathlib import Path

from plaivid_cli.domain.overview import LocalHostSample, NicSample, PhysicalNic

_DEVICE = re.compile(r"^[A-Za-z0-9_.:-]{1,32}$")
_COUNTERS = (
    "rx_bytes", "tx_bytes", "rx_packets", "tx_packets", "rx_errors", "tx_errors",
    "rx_dropped", "tx_dropped", "rx_crc_errors",
)


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="ascii")[:4096].strip()
    except (OSError, UnicodeError):
        return None


def _number(path: Path) -> int | None:
    text = _read(path)
    try:
        result = int(text) if text is not None else None
    except ValueError:
        return None
    return result if result is not None and result >= 0 else None


class LinuxMonitor:
    def __init__(self, proc: Path = Path("/proc"), sys_net: Path = Path("/sys/class/net")) -> None:
        self.proc = proc
        self.sys_net = sys_net
        self._cpu: tuple[int, int] | None = None
        self._nic: dict[str, tuple[float, int | None, int | None]] = {}

    def host(self) -> LocalHostSample:
        stat = _read(self.proc / "stat")
        cpu = None
        if stat:
            parts = stat.splitlines()[0].split()
            try:
                values = [int(part) for part in parts[1:]] if parts[0] == "cpu" else []
            except ValueError:
                values = []
            if len(values) >= 4:
                total = sum(values[:8])
                idle = values[3] + (values[4] if len(values) > 4 else 0)
                if self._cpu is not None:
                    total_delta = total - self._cpu[0]
                    idle_delta = idle - self._cpu[1]
                    if total_delta > 0 and 0 <= idle_delta <= total_delta:
                        cpu = 100 * (total_delta - idle_delta) / total_delta
                self._cpu = (total, idle)
        memory: dict[str, int] = {}
        for line in (_read(self.proc / "meminfo") or "").splitlines():
            key, _, value = line.partition(":")
            fields = value.strip().split()
            if fields and fields[0].isdigit() and (len(fields) == 1 or fields[1] == "kB"):
                memory[key] = int(fields[0]) * (1024 if len(fields) > 1 else 1)
        total_mem = memory.get("MemTotal")
        available = memory.get("MemAvailable")
        used = total_mem - available if total_mem is not None and available is not None and 0 <= available <= total_mem else None
        load = (_read(self.proc / "loadavg") or "").split()
        uptime = (_read(self.proc / "uptime") or "").split()
        try:
            loads = tuple(float(part) for part in load[:3]) if len(load) >= 3 else (None, None, None)
            up = float(uptime[0]) if uptime else None
            if any(value is not None and not math.isfinite(value) for value in (*loads, up)):
                raise ValueError("non-finite host measurement")
        except ValueError:
            loads, up = (None, None, None), None
        return LocalHostSample(
            hostname=socket.gethostname() or None, cpu_percent=cpu, memory_used=used,
            memory_total=total_mem, load1=loads[0], load5=loads[1], load15=loads[2],
            uptime_seconds=up,
        )

    def physical(self, name: str) -> bool:
        # Only names returned by the PVM NIC inventory may be sampled. Avoid traversal.
        return name not in {".", ".."} and bool(_DEVICE.fullmatch(name)) and (self.sys_net / name / "device").exists()

    def nics(self, devices: tuple[PhysicalNic, ...]) -> tuple[NicSample, ...]:
        now = time.monotonic()
        names = {device.name for device in devices if self.physical(device.name)}
        self._nic = {key: value for key, value in self._nic.items() if key in names}
        samples = []
        for name in sorted(names):
            base = self.sys_net / name
            counters = {key: _number(base / "statistics" / key) for key in _COUNTERS}
            previous = self._nic.get(name)
            rx, tx = counters["rx_bytes"], counters["tx_bytes"]
            rx_rate = tx_rate = None
            if previous and now > previous[0]:
                elapsed = now - previous[0]
                if rx is not None and previous[1] is not None and rx >= previous[1]:
                    rx_rate = (rx - previous[1]) / elapsed
                if tx is not None and previous[2] is not None and tx >= previous[2]:
                    tx_rate = (tx - previous[2]) / elapsed
            self._nic[name] = (now, rx, tx)
            samples.append(NicSample(
                name=name, **counters, state=_read(base / "operstate"),
                rx_bytes_per_second=rx_rate, tx_bytes_per_second=tx_rate,
            ))
        return tuple(samples)
