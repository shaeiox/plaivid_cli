"""Read-only monitoring facts. Missing measurements are None, never synthetic zeroes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LocalHostSample:
    hostname: str | None = None
    cpu_percent: float | None = None
    memory_used: int | None = None
    memory_total: int | None = None
    load1: float | None = None
    load5: float | None = None
    load15: float | None = None
    uptime_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class DashboardSample:
    host_name: str | None = None
    host_id: str | None = None
    cpu_info: tuple[str, ...] = ()
    ram_free_raw: str | None = None
    ram_used_raw: str | None = None
    ram_total_raw: str | None = None
    # Top-list and disk semantics require captured, versioned PVM evidence.
    vm_cpu: tuple[tuple[str, str], ...] = ()
    vm_ram: tuple[tuple[str, str], ...] = ()
    vm_network: tuple[tuple[str, str], ...] = ()
    vdis: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class PhysicalNic:
    name: str
    identifier: str | None = None
    mac: str | None = None
    ip: str | None = None
    gateway: str | None = None
    management: str | None = None
    redundancy: str | None = None


@dataclass(frozen=True, slots=True)
class NicSample:
    name: str
    rx_bytes: int | None = None
    tx_bytes: int | None = None
    rx_packets: int | None = None
    tx_packets: int | None = None
    rx_errors: int | None = None
    tx_errors: int | None = None
    rx_dropped: int | None = None
    tx_dropped: int | None = None
    rx_crc_errors: int | None = None
    state: str | None = None
    rx_bytes_per_second: float | None = None
    tx_bytes_per_second: float | None = None
