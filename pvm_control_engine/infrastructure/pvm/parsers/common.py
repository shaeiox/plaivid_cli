"""Shared safe numeric and XML text conversions used by PVM parsers."""

from __future__ import annotations

import xml.etree.ElementTree as ET


def _int(value: str | None) -> int | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        parsed = int(text)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def _detail_text(cpu: ET.Element | None, tag: str) -> str | None:
    """Text of ``cpu_info/cpu_detail_list/cpu_detail/<tag>`` (first logical CPU), or None."""
    if cpu is None:
        return None
    return (cpu.findtext(f"cpu_detail_list/cpu_detail/{tag}") or "").strip() or None


def _float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value.strip())
    except (AttributeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _average_cpu(usage: ET.Element | None) -> tuple[float | None, int | None]:
    if usage is None:
        return None, None
    values = [_float(cpu.text) for cpu in usage.findall("cpus/cpu")]
    valid = [value for value in values if value is not None]
    return (sum(valid) / len(valid), len(values)) if valid else (None, len(values) or None)


def _parse_vcpu(cpu: ET.Element | None) -> int | None:
    if cpu is None:
        return None
    vcpu = cpu.find("vcpu")
    if vcpu is None:
        return None
    parts = [_int(vcpu.findtext(key)) for key in ("socket", "core", "thread")]
    if any(value is None or value < 1 for value in parts):
        return None
    total = 1
    for part in parts:
        assert part is not None
        total *= part
    return total


def _real(value: str | None) -> float | None:
    """Signed decimal (temperatures may be negative); None for missing or non-finite text."""
    if value is None:
        return None
    try:
        parsed = float(value.strip())
    except (AttributeError, ValueError):
        return None
    return parsed if parsed == parsed and parsed not in (float("inf"), float("-inf")) else None


def _text(element: ET.Element | None, path: str) -> str | None:
    if element is None:
        return None
    value = (element.findtext(path) or "").strip()
    return value or None
