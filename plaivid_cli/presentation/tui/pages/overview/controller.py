"""Overview snapshot rendering and chart-history presentation."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from plaivid_cli.domain.models import (
    ApplicationSnapshot,
    CollectionStatus,
    InventoryData,
)
from plaivid_cli.presentation.charts import (
    CPU_MIN_SCALE,
    LOAD_COLOURS,
    Series,
    cpu_colour,
    stable_top,
)
from plaivid_cli.presentation.tui.pages.overview.components import (
    CPUCard,
    LoadCard,
    MemoryCard,
    NetworkCard,
    SystemCard,
)

from ...support import _section_status
from .presenter import cards, nic_details


class OverviewMixin:
    """Render overview data; it never calls providers or owns refresh policy."""

    def _render_charts(self) -> None:
        """CPU and load graphs from the 60-second overview history. Only real samples are plotted."""
        cpu = tuple(self._history.values["cpu"])
        loads = {
            "1m": tuple(self._history.values["load"]),
            "5m": tuple(self._history.values["load5"]),
            "15m": tuple(self._history.values["load15"]),
        }
        newest = max((points[-1][0] for points in (cpu, *loads.values()) if points), default=None)
        cpu_chart = self.query_one("#cpu-box", CPUCard).chart
        load_chart = self.query_one("#load-box", LoadCard).chart
        if newest is None:
            cpu_chart.reset("Waiting for samples")
            load_chart.reset("Waiting for samples")
            return
        palette = self._palette
        interval = self._overview_schedule.interval
        # Samples are averaged over at least two refresh intervals so a 1s refresh stays readable.
        max_gap = max(3.0 * interval, 1.0)
        min_bucket = 2.0 * interval

        cpu_now = cpu[-1][1] if cpu else None
        cpu_header = Text()
        cpu_header.append("CPU ", style=f"bold {palette.foreground}")
        cpu_header.append(
            "—" if cpu_now is None else f"{cpu_now:.1f}%",
            style=f"bold {cpu_colour(cpu_now, palette)}",
        )
        cpu_peak = max((value for _, value in cpu), default=None)
        self._cpu_scale = stable_top(cpu_peak, self._cpu_scale, floor=CPU_MIN_SCALE)
        cpu_header.append(f"   last 60 s · scale 0–{self._cpu_scale:g} %", style=palette.muted)
        cpu_chart.set_chart(
            series=(Series("cpu", cpu_colour(cpu_now, palette), cpu),),
            t_end=newest,
            scale_top=self._cpu_scale,
            header=cpu_header,
            max_gap=max_gap,
            min_bucket=min_bucket,
        )

        one_minute = loads["1m"]
        self._load_scale = stable_top(
            max((value for _, value in one_minute), default=None), self._load_scale
        )
        load_header = Text()
        load_header.append("Load ", style=f"bold {palette.foreground}")
        for label, points in loads.items():
            latest = points[-1][1] if points else None
            if label == "1m":
                load_header.append("● ", style=f"bold {LOAD_COLOURS[0]}")
            load_header.append(f"{label} ", style=palette.muted)
            load_header.append(
                "—" if latest is None else f"{latest:.2f}", style=f"bold {palette.foreground}"
            )
            load_header.append("   ")
        series = [Series("1m", LOAD_COLOURS[0], one_minute)]
        load_header.append(f"last 60 s · scale 0–{self._load_scale:g}", style=palette.muted)
        load_chart.set_chart(
            series=tuple(series),
            t_end=newest,
            scale_top=self._load_scale,
            header=load_header,
            max_gap=max_gap,
            min_bucket=min_bucket,
        )

    def _render_overview(self, snapshot: ApplicationSnapshot) -> None:
        self._visible_snapshot = snapshot
        self._history.add(snapshot)
        values = cards(snapshot, self._history, self._overview_schedule.interval)
        component_setters = {
            "cpu-card": self.query_one("#cpu-box", CPUCard).set_summary,
            "memory-card": self.query_one("#memory-box", MemoryCard).set_content,
            "load-card": self.query_one("#load-box", LoadCard).set_summary,
            "running-card": self.query_one("#load-box", LoadCard).set_running,
            "host-identity": self.query_one("#system-card", SystemCard).set_identity,
            "metrics-system": self.query_one("#system-card", SystemCard).set_metrics,
        }
        for widget_id, text in values.items():
            self._put(widget_id, text, setter=component_setters.get(widget_id))
        self._render_charts()
        devices, detail = nic_details(snapshot, self._nic_selected)
        names = tuple(item.name for item in devices)
        if self._nic_selected not in names:
            self._nic_selected = names[0] if names else None
        network = self.query_one("#network-box", NetworkCard)
        network.set_interfaces(names, self._nic_selected)
        self._nic_tab_names = names
        self._put("nic-detail", detail, setter=network.set_detail)

    def select_nic(self, name: str) -> None:
        """Receive a page-component selection and present its latest sample."""
        if name not in self._nic_tab_names:
            return
        self._nic_selected = name
        _, detail = (
            nic_details(self._visible_snapshot, self._nic_selected)
            if self._visible_snapshot
            else ((), "No sample")
        )
        network = self.query_one("#network-box", NetworkCard)
        self._put("nic-detail", detail, setter=network.set_detail)

    def _publish_snapshot(self, snapshot: ApplicationSnapshot) -> None:
        self._render_desktops(snapshot.section("desktops"))
        self._render_overview(snapshot)
        inventory_section = snapshot.section("inventory")
        if inventory_section is None or inventory_section.generation == self._inventory_generation:
            self._render_host(snapshot)
            return
        self._inventory_generation = inventory_section.generation
        self._inventory_section = inventory_section
        inventory = None
        if inventory_section is not None:
            value = inventory_section.value or inventory_section.last_good_value
            if isinstance(value, InventoryData):
                inventory = value
        self._inventory = inventory
        self._records = {record.uuid: record for record in inventory.records} if inventory else {}
        self._filter_vms()
        if inventory is not None:
            self.query_one("#vm-count", Static).update(str(len(inventory.records)))
            self.query_one("#process-count", Static).update(
                str(sum(record.process_seen for record in inventory.records))
            )
        else:
            self.query_one("#vm-count", Static).update("—")
            self.query_one("#process-count", Static).update("—")
        if inventory_section is None:
            quality = "Unavailable"
        else:
            quality = inventory_section.status.value.replace("_", " ").title()
            if inventory_section.quality_issues:
                quality += f" · {len(inventory_section.quality_issues)} issue(s)"
        self.query_one("#inventory-quality", Static).update(quality)
        status = _section_status(inventory_section)
        self.query_one("#inventory-quality", Static).styles.color = (
            self._palette.success
            if inventory_section and inventory_section.status is CollectionStatus.CURRENT
            else self._palette.warning
        )
        self.query_one("#notice", Static).update(
            f"Inventory {status} · generation {inventory_section.generation if inventory_section else '—'} · "
            "object states and process observations are shown separately"
        )
        self._render_host(snapshot)
