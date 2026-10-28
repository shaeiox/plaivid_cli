"""Presentation layer - turns data into styled terminal output.

Pure formatting only: it never calls the transport or mutates state, so it can
be restyled freely. All width maths ignore ANSI escapes so colored and plain
output align identically.
"""

import re
import shutil

from . import theme
from .theme import BOX
from .version import __version__

_ANSI = re.compile(r"\033\[[0-9;]*m")


def _vis(s):
    return len(_ANSI.sub("", s))


def term_width():
    try:
        return shutil.get_terminal_size((100, 24)).columns
    except Exception:
        return 100


def width():
    """Content (block) width - frames fill the whole terminal width."""
    return max(60, term_width())


def margin():
    """Left padding to center the block (0 now that it spans full width)."""
    return max(0, (term_width() - width()) // 2)


def center(block):
    """Indent every line of ``block`` so the whole block sits centered."""
    pad = " " * margin()
    return "\n".join(pad + line for line in block.split("\n"))


def _pad(s, n):
    return s + " " * max(0, n - _vis(s))


def frame(title, lines, color_fn=theme.muted):
    """Draw a rounded box around ``lines`` with ``title`` in the top border."""
    w = width()
    inner = w - 2
    cap = " %s " % title if title else ""
    top = (color_fn(BOX["tl"]) + color_fn(cap)
           + color_fn(BOX["h"] * max(0, inner - _vis(cap)))
           + color_fn(BOX["tr"]))
    out = [top]
    for ln in lines:
        out.append(color_fn(BOX["v"]) + " " + _pad(ln, inner - 2)
                   + " " + color_fn(BOX["v"]))
    out.append(color_fn(BOX["bl"]) + color_fn(BOX["h"] * inner)
               + color_fn(BOX["br"]))
    return "\n".join(out)


# --- banner ------------------------------------------------------------------
def banner():
    bar = theme.secondary("▀" * 3) if theme._unicode else "###"
    title = (theme.bold(theme.primary("Plaivid")) + theme.secondary(" CLI")
             + theme.muted("  v" + __version__))
    sub = theme.muted("  PVM virtual-machine control")
    return "\n%s %s\n%s\n" % (bar, title, sub)


# --- host panel --------------------------------------------------------------
def _bar(pct, n=16):
    if pct is None:
        return theme.muted("-" * n)
    filled = int(round(min(max(pct, 0), 100) / 100.0 * n))
    glyph = "█" if theme._unicode else "#"
    fn = theme.success if pct < 70 else theme.warning if pct < 90 else theme.error
    return fn(glyph * filled) + theme.muted(("░" if theme._unicode else ".")
                                            * (n - filled))


def host_panel(info):
    if info.get("error"):
        return frame("Host", [theme.error(theme.glyph("err") + " "
                     + info["error"])], theme.error)
    lines = []
    head = "%s   %s   sball: %s" % (
        theme.bold(info.get("name", "?")),
        theme.accent(info.get("ip", "")),
        theme.success(info.get("sball_state", "")))
    lines.append(head)
    ver = info.get("version", "")
    if ver:
        lines.append(theme.muted("PVM %s   %s   load %s"
                     % (ver, info.get("host_time", ""), info.get("load1", ""))))
    cpu = info.get("cpu_pct")
    if cpu is not None:
        lines.append("CPU  %s %s  (%d cores)"
                     % (_bar(cpu), _val("%.0f%%" % cpu),
                        info.get("cpu_count", 0)))
    ram = info.get("ram_pct")
    if ram is not None:
        lines.append("RAM  %s %s  (%.0f/%.0f GB)"
                     % (_bar(ram), _val("%.0f%%" % ram),
                        info.get("ram_used_gb") or 0,
                        info.get("ram_total_gb") or 0))
    sp = info.get("store_used_pct")
    if sp is not None:
        lines.append("Disk %s %s  (%.0f GB total)"
                     % (_bar(sp), _val("%.0f%%" % sp),
                        info.get("store_total_gb") or 0))
    return frame("Host  %s" % theme.glyph("dot"), lines, theme.primary)


def _val(s):
    return theme.accent(_right(s, 4))


def _right(s, n):
    return " " * max(0, n - len(s)) + s


# --- VM table ----------------------------------------------------------------
def vm_table(vms, sort_label=None):
    if not vms:
        return frame("Virtual machines", [theme.muted("no VMs found")],
                     theme.secondary)
    running = sum(1 for v in vms if v.running)
    wn = min(max([len(v.name) for v in vms] + [4]), 30)
    # Pad the PLAIN text first, then color it - padding a colored string
    # counts the escape codes as width and collapses the columns.
    fmt = "%-3s %s %-*s %-8s %4s %5s %-12s %-8s %-6s %s"
    rows = [theme.muted(fmt % ("#", " ", wn, "NAME", "STATE", "CPU", "MEM",
                               "UPTIME", "PID", "SPICE", "UUID"))]
    for v in vms:
        fn, gl = theme.state_style(v.state)
        name = v.name if len(v.name) <= wn else v.name[:wn - 1] + "…"
        port = str(v.port or "-").ljust(6)
        rows.append("%s %s %s %s %s %s %s %s %s %s" % (
            theme.bold(str(v.index).ljust(3)),
            fn(gl),
            fn(name.ljust(wn)),
            fn((v.state or "-").ljust(8)),
            theme.fg(str(v.vcpu if v.vcpu is not None else "-").rjust(4)),
            theme.fg(v.mem_human.rjust(5)),
            theme.muted((v.uptime or "-").ljust(12)),
            theme.accent(str(v.pid or "-").ljust(8)),
            theme.accent(port) if v.running else theme.muted(port),
            theme.muted(v.uuid)))
    title = "Virtual machines  %s  %s running / %s total" % (
        theme.glyph("dot"), theme.success(running), len(vms))
    if sort_label:
        title += "  %s  sorted by %s" % (theme.glyph("dot"), sort_label)
    return frame(title, rows, theme.secondary)


# --- messages ----------------------------------------------------------------
def _panel(title, lines, panel_width, color_fn=theme.muted):
    """Draw a fixed-width panel used by the responsive dashboard grid."""
    panel_width = max(8, panel_width)
    inner = panel_width - 2
    cap = " %s " % title
    top = (color_fn(BOX["tl"]) + color_fn(cap)
           + color_fn(BOX["h"] * max(0, inner - _vis(cap)))
           + color_fn(BOX["tr"]))
    out = [top]
    for line in lines:
        # Dashboard content uses short labels; clip plain width before padding.
        if _vis(line) > inner - 2:
            line = _ANSI.sub("", line)[:max(0, inner - 5)] + "..."
        out.append(color_fn(BOX["v"]) + " " + _pad(line, inner - 2)
                   + " " + color_fn(BOX["v"]))
    out.append(color_fn(BOX["bl"]) + color_fn(BOX["h"] * inner)
               + color_fn(BOX["br"]))
    return out


def _hstack(boxes, gap=1):
    """Join panel line-arrays horizontally, padding to a shared height."""
    if not boxes:
        return []
    height = max(len(box) for box in boxes)
    widths = [max((_vis(line) for line in box), default=0) for box in boxes]
    result = []
    for row in range(height):
        cells = []
        for i, box in enumerate(boxes):
            line = box[row] if row < len(box) else " " * widths[i]
            cells.append(_pad(line, widths[i]))
        result.append((" " * gap).join(cells))
    return result


def _sparkline(values, width=12):
    """Tiny trend plot; no history means a calm placeholder line."""
    if not values:
        return theme.muted("·" * width if theme._unicode else "-" * width)
    glyphs = "▁▂▃▄▅▆▇█" if theme._unicode else "._-:=+*#"
    vals = list(values)[-width:]
    lo, hi = min(vals), max(vals)
    span = hi - lo or 1.0
    return theme.accent("".join(glyphs[int((v - lo) / span * (len(glyphs)-1))]
                                 for v in vals).rjust(width))


def dashboard(info, vms, sort_label=None, status="", selected=None,
              cpu_history=None, load_history=None, refreshed="on demand"):
    """Responsive dashboard layout, composed only from already-loaded data."""
    import datetime

    screen = max(60, term_width())
    gap = 1
    running = sum(1 for vm in vms if vm.running)
    stopped = sum(1 for vm in vms if vm.state == "stopped")
    off = sum(1 for vm in vms if vm.state == "off")
    now = datetime.datetime.now().strftime("%H:%M:%S")
    title = (theme.bold(theme.primary("Plaivid CLI"))
             + theme.muted(" v" + __version__ + "   PVM virtual-machine control"))
    shortcuts = theme.muted("[?] Help  [/] Search  [r] Refresh  [q] Quit  " + now)
    lines = [title, shortcuts]

    # Seven concise metric cards. Host uptime/network rates are intentionally
    # absent here: the main refresh endpoint does not supply those values.
    total_width = screen
    card_columns = 7 if screen >= 140 else (4 if screen >= 90 else 2)
    card_width = (total_width - gap * (card_columns - 1)) // card_columns
    host_lines = [theme.bold(info.get("name") or "unknown"),
                  (info.get("ip") or "IP unavailable"),
                  "PVM " + (info.get("version") or "-")]
    cpu = info.get("cpu_pct")
    cpu_lines = [theme.bold("--" if cpu is None else "%.0f%%" % cpu),
                 "%s cores" % (info.get("cpu_count") or "-"),
                 _sparkline(cpu_history)]
    ram = info.get("ram_pct")
    ram_lines = [theme.bold("--" if ram is None else "%.0f%%" % ram),
                 "%.0f/%.0f GB" % (info.get("ram_used_gb") or 0,
                                   info.get("ram_total_gb") or 0), _bar(ram, 8)]
    disk = info.get("store_used_pct")
    disk_lines = [theme.bold("--" if disk is None else "%.0f%%" % disk),
                  "%.0f GB total" % (info.get("store_total_gb") or 0),
                  _bar(disk, 8)]
    load = " / ".join(str(info.get(k) or "-") for k in
                      ("load1", "load5", "load15"))
    card_specs = [
        ("HOST", host_lines, theme.primary),
        ("CPU", cpu_lines, theme.primary),
        ("RAM", ram_lines, theme.primary),
        ("DISK", disk_lines, theme.warning),
        ("VMs", [theme.success("%d running" % running),
                  "/ %d total" % len(vms)], theme.primary),
        ("LOAD AVG", [load, _sparkline(load_history)], theme.primary),
        ("UPTIME", [info.get("uptime_human") or "not reported",
                    "host uptime"], theme.primary),
    ]
    cards = [_panel(label, body, card_width, color)
             for label, body, color in card_specs]
    for offset in range(0, len(cards), card_columns):
        lines.extend(_hstack(cards[offset:offset + card_columns], gap=gap))

    # VM table, clipped to the actual left-column width, with a context rail.
    rail_width = max(26, min(34, screen // 4))
    left_width = screen - rail_width - gap
    if screen < 120:
        left_width, rail_width = screen, 0
    title_sort = "Sorted by " + (sort_label or "default order")
    table_title = _panel("VIRTUAL MACHINES  " + title_sort, [], left_width,
                         theme.secondary)
    widths_cols = [3, max(8, int(left_width * .22)), 9, 4, 5, 12, 8, 6]
    fixed = sum(widths_cols) + len(widths_cols) * 2 + 3
    uuid_width = max(4, left_width - fixed - 2)
    headings = ["ID", "NAME", "STATE", "CPU", "MEM", "UPTIME", "PID", "SPICE", "UUID"]
    header = " ".join(value.ljust(widths_cols[i]) for i, value in enumerate(headings[:-1]))
    header += " " + "UUID"[:uuid_width].ljust(uuid_width)
    table_rows = [theme.muted(header)]
    for vm in vms:
        fn, glyph = theme.state_style(vm.state)
        name = vm.name[:widths_cols[1]]
        fields = [str(vm.index or "-")[:3].ljust(3), name.ljust(widths_cols[1]),
                  (glyph + " " + (vm.state or "?")).ljust(widths_cols[2]),
                  str(vm.vcpu if vm.vcpu is not None else "-").rjust(4),
                  vm.mem_human.rjust(5), (vm.uptime or "-")[:12].ljust(12),
                  str(vm.pid or "-")[:8].ljust(8), str(vm.port or "-")[:6].ljust(6),
                  (vm.uuid or "-")[:uuid_width]]
        row = " ".join(fields)
        table_rows.append(fn(row))
    if not vms:
        table_rows.append(theme.muted("No virtual machines found"))
    table_box = _panel("VIRTUAL MACHINES  " + title_sort, table_rows,
                       left_width, theme.secondary)

    focus = selected or (vms[0] if vms else None)
    rail = []
    if focus:
        state_fn, glyph = theme.state_style(focus.state)
        rail.append(_panel("SELECTED VM", [
            state_fn(glyph + " " + focus.name), state_fn(focus.state),
            "Uptime: " + (focus.uptime or "-"),
            "CPUs: %s  Memory: %s" % (focus.vcpu or "-", focus.mem_human),
            "PID: %s  SPICE: %s" % (focus.pid or "-", focus.port or "-"),
            "UUID: " + (focus.uuid or "-"),
        ], rail_width, theme.primary))
    else:
        rail.append(_panel("SELECTED VM", ["Select a VM with a command"],
                           rail_width, theme.primary))
    rail.append(_panel("RESOURCES", [
        "CPU  %s %s" % (_bar(cpu, 9), "--" if cpu is None else "%.0f%%" % cpu),
        "RAM  %s %s" % (_bar(ram, 9), "--" if ram is None else "%.0f%%" % ram),
        "Disk %s %s" % (_bar(disk, 9), "--" if disk is None else "%.0f%%" % disk),
        "Network rates: use overview",
    ], rail_width, theme.accent))
    rail.append(_panel("QUICK ACTIONS", [
        "start <id/name>   Start VM", "stop <id/name>    Graceful stop",
        "kill <id/name>    Force stop", "reset <id/name>   Reset VM",
        "pause/resume      VM state action",
    ], rail_width, theme.secondary))
    rail_lines = []
    if rail_width:
        # Stack the right-rail panels within a single responsive column.
        rail_lines = []
        for panel in rail:
            if rail_lines:
                rail_lines.append(" " * rail_width)
            rail_lines.extend(panel)
    else:
        rail_lines = []
        for panel in rail:
            if rail_lines:
                rail_lines.append("")
            rail_lines.extend(panel)
    if rail_width:
        while len(table_box) < len(rail_lines):
            empty = (theme.muted(BOX["v"]) + " "
                     + " " * max(0, left_width - 4) + " "
                     + theme.muted(BOX["v"]))
            table_box.insert(-1, empty)
        rail_lines += [" " * rail_width] * max(0, len(table_box) - len(rail_lines))
        lines.extend(_hstack([table_box, rail_lines]))
    else:
        lines.extend(table_box)
        lines.extend(rail_lines)

    # Compact three-column help/footer row adapts to small terminals.
    col_gap = 1
    col_width = max(12, (screen - 2 * col_gap) // 3)
    commands = ["list/status  Refresh inventory", "sort <field>  Reorder list",
                "overview     Live metrics", "health       Capacity checks",
                "show <vm>    VM details", "log [N]      Audit history"]
    actions_help = ["start  Power on", "stop   Graceful shutdown",
                    "kill   Force power-off", "reset  Hard reset",
                    "pause / resume"]
    legend = [theme.success("● started   running"),
              theme.warning("● stopped  stopped"),
              theme.error("● off      powered off"),
              "VMs %d total | %d running | %d stopped | %d off" %
              (len(vms), running, stopped, off)]
    footer = _hstack([
        _panel("COMMANDS", commands, col_width, theme.secondary),
        _panel("VM ACTIONS", actions_help, col_width, theme.secondary),
        _panel("STATUS LEGEND", legend, screen - 2 * (col_width + col_gap),
               theme.primary),
    ], gap=col_gap)
    lines.extend(footer)
    if status:
        lines.append(status)
    host = info.get("name") or "PVM"
    ip = info.get("ip") or ""
    status_left = "Connected to: %s (%s)" % (host, ip)
    status_right = "Plaivid CLI v" + __version__
    status_center = "Refreshed: " + str(refreshed)
    status_line = status_left
    if screen >= 90:
        remain = max(1, screen - _vis(status_left) - _vis(status_right) - 2)
        status_line += " " * max(1, (remain - _vis(status_center)) // 2)
        status_line += status_center
        status_line += " " * max(1, screen - _vis(status_line) - _vis(status_right))
        status_line += status_right
    lines.append(theme.primary(status_line[:screen]))
    return "\n".join(lines)


def ok(msg):
    return theme.success(theme.glyph("ok") + " ") + msg


def err(msg):
    return theme.error(theme.glyph("err") + " ") + msg


def info(msg):
    return theme.accent(theme.glyph("dot") + " ") + msg


def warn(msg):
    return theme.warning(theme.glyph("ask") + " ") + msg


def hint(msg):
    return theme.muted(msg)


# --- live overview -----------------------------------------------------------
def human_rate(bps):
    if bps is None:
        return theme.muted("   --   ")
    v = float(bps)
    for unit in ("B", "K", "M", "G"):
        if v < 1024:
            return "%6.1f %s/s" % (v, unit)
        v /= 1024
    return "%6.1f T/s" % v


def _net_rates(snap, prev):
    """Per-interface (rx_rate, tx_rate) in bytes/s between two snapshots."""
    rates = {}
    if not prev:
        return rates
    dt = max(0.001, snap.get("ts", 0) - prev.get("ts", 0))
    for name, cur in snap.get("net", {}).items():
        old = prev.get("net", {}).get(name)
        if not old:
            continue
        rx = max(0.0, cur["rx"] - old["rx"]) / dt
        tx = max(0.0, cur["tx"] - old["tx"]) / dt
        rates[name] = (rx, tx, cur.get("type", ""))
    return rates


def _short(path, n=34):
    if len(path) <= n:
        return path
    return "…" + path[-(n - 1):]


def _host_panel(snap, spin):
    cores_l = snap.get("logical_cores") or 0
    cores_p = snap.get("physical_cores") or 0
    load1 = snap.get("load1") or 0.0
    load_pct = (100.0 * load1 / cores_l) if cores_l else 0.0
    lines = []
    ident = "%s   %s   up %s   sball: %s" % (
        theme.bold(snap.get("hostname") or "host"),
        theme.muted("PVM " + (snap.get("pvm_version") or "?")
                    + ((" / " + snap["os_version"]) if snap.get("os_version") else "")),
        snap.get("uptime_human") or "?",
        theme.success(snap.get("sball_state") or "?"))
    lines.append(ident)
    lines.append("CPU    %s %s   (%d physical / %d logical cores)"
                 % (_bar(snap.get("cpu_pct")),
                    _val("%.0f%%" % (snap.get("cpu_pct") or 0)), cores_p, cores_l))
    lines.append("Load   %s %s   (1m %.2f  5m %.2f  15m %.2f)"
                 % (_bar(load_pct), _val("%.0f%%" % load_pct),
                    load1, snap.get("load5") or 0, snap.get("load15") or 0))
    lines.append("RAM    %s %s   (%.1f / %.1f GB)"
                 % (_bar(snap.get("mem_pct")),
                    _val("%.0f%%" % (snap.get("mem_pct") or 0)),
                    snap.get("mem_used_gb") or 0, snap.get("mem_total_gb") or 0))
    if (snap.get("swap_total_gb") or 0) > 0.01:
        lines.append("Swap   %s %s   (%.1f / %.1f GB)"
                     % (_bar(snap.get("swap_pct")),
                        _val("%.0f%%" % (snap.get("swap_pct") or 0)),
                        snap.get("swap_used_gb") or 0, snap.get("swap_total_gb") or 0))
    else:
        lines.append("Swap   %s" % theme.muted("disabled"))
    return frame("Host  %s" % spin, lines, theme.primary)


def _vm_panel(agg):
    counts = "Total %s      %s running      %s stopped      %s off" % (
        theme.bold(str(agg["total"])),
        theme.success(str(agg["running"])),
        theme.muted(str(agg["stopped"])),
        theme.error(str(agg["off"])))
    if agg.get("paused"):
        counts += "      %s paused" % theme.warning(str(agg["paused"]))
    alloc = ("vCPU   %s running / %s allocated        "
             "Memory   %.1f running / %.1f GB allocated" % (
                 theme.accent(str(agg["vcpu_run"])),
                 theme.accent(str(agg["vcpu_total"])),
                 agg["mem_run_mb"] / 1024.0, agg["mem_total_mb"] / 1024.0))
    return frame("Virtual machines", [counts, alloc], theme.secondary)


def _net_panel(snap, rates, tapmap, measuring):
    lines = []
    if measuring:
        lines.append(theme.muted("measuring throughput..."))
        return frame("Network", lines, theme.accent)

    phys = {n: r for n, r in rates.items() if r[2] == "physical"}
    up_rx = sum(r[0] for r in phys.values())
    up_tx = sum(r[1] for r in phys.values())
    lines.append("Uplink   %s %s    %s %s" % (
        theme.accent("down"), human_rate(up_rx),
        theme.accent("up"), human_rate(up_tx)))
    for name in sorted(phys):
        rx, tx, _ = phys[name]
        st = snap.get("net", {}).get(name, {}).get("state", "")
        stt = (st or "-").ljust(5)
        stc = theme.success(stt) if st == "up" else theme.muted(stt)
        lines.append("  %s %s  %s %s   %s %s"
                     % (name.ljust(8), stc, theme.muted("down"),
                        human_rate(rx), theme.muted("up"), human_rate(tx)))

    # per-VM traffic (summed over each VM's taps)
    per_vm = {}
    for name, (rx, tx, typ) in rates.items():
        vm = tapmap.get(name)
        if not vm:
            continue
        a = per_vm.setdefault(vm, [0.0, 0.0])
        a[0] += rx
        a[1] += tx
    talkers = sorted(per_vm.items(), key=lambda kv: kv[1][0] + kv[1][1],
                     reverse=True)
    talkers = [t for t in talkers if t[1][0] + t[1][1] > 1][:10]
    lines.append("")
    lines.append(theme.muted("Per VM            %12s %12s" % ("DOWN", "UP")))
    if not talkers:
        lines.append(theme.muted("  no VM network traffic"))
    else:
        for vm, (rx, tx) in talkers:
            lines.append("  %-16s %s %s"
                         % (vm[:16], theme.accent(human_rate(rx)),
                            theme.accent(human_rate(tx))))
    return frame("Network", lines, theme.accent)


def _storage_panel(snap):
    items = snap.get("storage", [])
    if not items:
        return frame("Storage", [theme.muted("no storage data")], theme.warning)
    def gb(v):
        return ("%.1f" % v) if v < 100 else ("%.0f" % v)

    lines = []
    for st in items:
        usage = ("%s / %s GB" % (gb(st["used_gb"]), gb(st["total_gb"]))).ljust(16)
        lines.append("%-10s %s %s  %s %s"
                     % (st["kind"], _bar(st["pct"]),
                        _val("%.0f%%" % st["pct"]), usage,
                        theme.muted(_short(st["mount"]))))
    ds = [s for s in items if s["kind"] == "DataStore"]
    if ds:
        tot = sum(s["total_gb"] for s in ds)
        used = sum(s["used_gb"] for s in ds)
        lines.append(theme.muted(
            "DataStore total: %.0f / %.0f GB across %d store(s)"
            % (used, tot, len(ds))))
    return frame("Storage", lines, theme.warning)


def overview(snap, prev, tapmap, agg, spin):
    """Render the live monitor with the same responsive panel language."""
    if snap.get("error"):
        return frame("Live monitoring", [err(snap["error"])], theme.error)

    screen = max(60, term_width())
    lines = [theme.bold(theme.primary("LIVE OVERVIEW"))
             + theme.muted("   %s   %s   PVM %s" % (
                 snap.get("hostname") or "host",
                 snap.get("uptime_human") or "uptime unavailable",
                 snap.get("pvm_version") or "?"))]
    cpu = snap.get("cpu_pct")
    ram = snap.get("mem_pct")
    load1 = float(snap.get("load1") or 0)
    cores = snap.get("logical_cores") or 0
    load_pct = min(100.0, 100.0 * load1 / cores) if cores else 0
    cardspec = [
        ("CPU", ["--" if cpu is None else "%.0f%%" % cpu,
                 "%s logical cores" % cores,
                 "%s physical cores" % (snap.get("physical_cores") or "-")], theme.primary),
        ("LOAD", ["1m: %.2f  5m: %.2f" % (
            float(snap.get("load1") or 0), float(snap.get("load5") or 0)),
            "15m: %.2f" % float(snap.get("load15") or 0),
            _bar(load_pct, 12)], theme.primary),
        ("MEMORY", ["--" if ram is None else "%.0f%%" % ram,
                    "%.1f / %.1f GB" % (snap.get("mem_used_gb") or 0,
                                        snap.get("mem_total_gb") or 0),
                    _bar(ram, 12)], theme.primary),
        ("SWAP", ["disabled" if (snap.get("swap_total_gb") or 0) <= 0.01
                  else "%.0f%%" % (snap.get("swap_pct") or 0),
                  "%.1f / %.1f GB" % (snap.get("swap_used_gb") or 0,
                                      snap.get("swap_total_gb") or 0)], theme.warning),
    ]
    columns = 4 if screen >= 100 else 2
    cw = (screen - columns + 1) // columns
    cards = [_panel(name, content, cw, color)
             for name, content, color in cardspec]
    for i in range(0, len(cards), columns):
        lines.extend(_hstack(cards[i:i + columns]))

    vm_lines = ["Total %s | %s running | %s stopped | %s off" % (
        agg.get("total", 0), agg.get("running", 0), agg.get("stopped", 0),
        agg.get("off", 0)),
        "vCPU %s/%s allocated | RAM %.1f/%.1f GB allocated" % (
            agg.get("vcpu_run", 0), agg.get("vcpu_total", 0),
            (agg.get("mem_run_mb", 0) or 0) / 1024.0,
            (agg.get("mem_total_mb", 0) or 0) / 1024.0)]
    lines.extend(_panel("VIRTUAL MACHINES", vm_lines, screen, theme.secondary))

    rates = _net_rates(snap, prev)
    network_lines = []
    if not prev:
        network_lines.append("Measuring throughput on next refresh...")
    else:
        phys = {name: rate for name, rate in rates.items()
                if rate[2] == "physical"}
        network_lines.append("Uplink  down %s   up %s" % (
            human_rate(sum(rate[0] for rate in phys.values())),
            human_rate(sum(rate[1] for rate in phys.values()))))
        for name in sorted(phys):
            rx, tx, _kind = phys[name]
            state = snap.get("net", {}).get(name, {}).get("state") or "-"
            network_lines.append("%-12s %-6s  ↓ %s  ↑ %s" % (
                name, state, human_rate(rx), human_rate(tx)))
        per_vm = {}
        for name, (rx, tx, _kind) in rates.items():
            vm_name = tapmap.get(name)
            if vm_name:
                totals = per_vm.setdefault(vm_name, [0.0, 0.0])
                totals[0] += rx
                totals[1] += tx
        for vm_name, (rx, tx) in sorted(
                per_vm.items(), key=lambda item: sum(item[1]), reverse=True)[:5]:
            network_lines.append("%-14s ↓ %s  ↑ %s" % (
                vm_name[:14], human_rate(rx), human_rate(tx)))
        if len(network_lines) == 1:
            network_lines.append("No physical interface rates available")

    storage_lines = []
    for item in snap.get("storage", []):
        storage_lines.append("%-10s %s %s / %.1f GB  %s" % (
            item.get("kind", "disk"), _bar(item.get("pct"), 8),
            "%.1f" % item.get("used_gb", 0), item.get("total_gb", 0),
            _short(item.get("mount", ""), 20)))
    if not storage_lines:
        storage_lines.append("No storage data available")

    if screen >= 100:
        half = (screen - 1) // 2
        lower = _hstack([_panel("NETWORK", network_lines, half, theme.accent),
                         _panel("STORAGE", storage_lines,
                                screen - half - 1, theme.warning)])
        lines.extend(lower)
    else:
        lines.extend(_panel("NETWORK", network_lines, screen, theme.accent))
        lines.extend(_panel("STORAGE", storage_lines, screen, theme.warning))
    lines.append(theme.muted("Refresh interval is controlled by PLAIVID_REFRESH"))
    return "\n".join(lines)


# --- VM detail ---------------------------------------------------------------
def vm_detail(d):
    fn, gl = theme.state_style(d.get("state"))

    g = []
    g.append("UUID     %s" % theme.muted(d["uuid"]))
    g.append("State    %s %s      Host  %s      HA  %s"
             % (fn(gl), fn(d["state"]), theme.accent(d["host"] or "-"),
                theme.accent(d["ha"] or "-")))
    if d.get("pid"):
        g.append("PID      %s      Uptime  %s"
                 % (theme.accent(str(d["pid"])), theme.muted(d.get("uptime") or "-")))
    g.append("Enabled  %s      Auto-start  %s      Always-on  %s"
             % (d["enabled"] or "-", d["auto_start"] or "-", d["always_on"] or "-"))
    g.append("Created  %s      Modified  %s"
             % (theme.muted(d["created"] or "-"), theme.muted(d["modified"] or "-")))
    if d["description"]:
        g.append("Note     %s" % d["description"])
    general = frame("VM  %s  %s" % (theme.glyph("dot"), theme.bold(d["name"])),
                    g, theme.primary)

    mem_g = (d["mem_mb"] or 0) / 1024.0
    c = [
        "vCPU     %s   (%s = sockets x cores x threads)"
        % (theme.accent(str(d["vcpu"])), d["vcpu_topo"]),
        "Memory   %s GB" % theme.accent("%.1f" % mem_g),
        "CPU      %s      Machine  %s"
        % (d["cpu_model"] or "-", theme.muted(d["machine"] or "-")),
        "Firmware %s      QEMU  %s"
        % ("UEFI" if d["uefi"] == "enable" else "BIOS", d["qemu"] or "-"),
    ]
    compute = frame("Compute", c, theme.secondary)

    drows = [theme.muted("%-14s %-7s %-8s %-5s %s"
                         % ("NAME", "MEDIA", "BUS", "BOOT", "CACHE"))]
    for dk in d["disks"]:
        drows.append("%-14s %-7s %-8s %-5s %s"
                     % (dk["name"][:14], dk["media"], dk["controller"],
                        dk["boot"], dk["cache"]))
    if not d["disks"]:
        drows.append(theme.muted("none"))
    disks = frame("Disks", drows, theme.accent)

    nrows = [theme.muted("%-6s %-8s %-18s %-16s %s"
                         % ("NAME", "DEVICE", "MAC", "TAP", "ENABLED"))]
    for na in d["nics"]:
        nrows.append("%-6s %-8s %-18s %-16s %s"
                     % (na["name"], na["device"], na["mac"], na["tap"],
                        na["enable"]))
    if not d["nics"]:
        nrows.append(theme.muted("none"))
    nics = frame("Network", nrows, theme.accent)

    con = d.get("console") or {}
    if con:
        endpoint = "%s://%s:%s" % (con.get("type") or "spice",
                                   con.get("bind") or "?", con.get("port") or "?")
        crows = [
            "Type     %s      Port  %s"
            % (con.get("type") or "-", theme.accent(con.get("port") or "-")),
            "Endpoint %s" % theme.accent(endpoint),
            "Password %s      TLS  %s"
            % (con.get("password") or "-", con.get("tls") or "-"),
        ]
    else:
        crows = [theme.muted("no console configured")]
    console = frame("Console", crows, theme.secondary)

    return "\n".join([general, compute, disks, nics, console])


# --- health & audit ----------------------------------------------------------
def _level_style(level):
    if level == "ok":
        return theme.success, theme.glyph("ok")
    if level == "warn":
        return theme.warning, theme.glyph("ask")
    return theme.error, theme.glyph("err")


def health(report):
    v = report["verdict"]
    fn, gl = _level_style(v)
    word = {"ok": "HEALTHY", "warn": "WARNINGS", "crit": "CRITICAL"}[v]
    lines = ["%s  overall: %s" % (fn(gl), theme.bold(fn(word))), ""]
    for c in report["checks"]:
        cfn, cgl = _level_style(c["level"])
        lines.append("%s %s  %s"
                     % (cfn(cgl), c["name"].ljust(18), theme.muted(c["detail"])))
    return frame("Health & capacity", lines, fn)


def log_view(entries, summary):
    s = summary
    span = "%s  →  %s" % (s["span"][0] or "-", s["span"][1] or "-")
    fails_fn = theme.error if s["failures"] else theme.success
    srows = [
        "Actions  %s      Failures  %s"
        % (theme.bold(str(s["total"])), fails_fn(str(s["failures"]))),
        "Window   %s" % theme.muted(span),
        "Top cmd  %s" % ", ".join("%s(%d)" % (c, n) for c, n in s["top_cmds"]),
        "Users    %s" % ", ".join("%s(%d)" % (u, n) for u, n in s["top_users"]),
    ]
    summary_panel = frame("Audit summary", srows, theme.secondary)

    rows = [theme.muted("%-19s %-9s %-15s %-22s %s"
                        % ("TIME", "USER", "IP", "COMMAND", "RESULT"))]
    for e in entries:
        rfn = theme.success if e["ok"] else theme.error
        rows.append("%-19s %-9s %-15s %-22s %s"
                    % (e["time"], e["user"][:9], e["ip"][:15], e["cmd"][:22],
                       rfn(e["result"])))
    if not entries:
        rows.append(theme.muted("no recent user actions"))
    table = frame("Recent actions", rows, theme.accent)
    return summary_panel + "\n" + table
