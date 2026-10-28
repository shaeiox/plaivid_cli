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
def vm_table(vms):
    if not vms:
        return frame("Virtual machines", [theme.muted("no VMs found")],
                     theme.secondary)
    running = sum(1 for v in vms if v.running)
    wn = min(max([len(v.name) for v in vms] + [4]), 30)
    # Pad the PLAIN text first, then color it - padding a colored string
    # counts the escape codes as width and collapses the columns.
    fmt = "%-3s %s %-*s %-8s %4s %5s %-12s %-8s %s"
    rows = [theme.muted(fmt % ("#", " ", wn, "NAME", "STATE", "CPU", "MEM",
                               "UPTIME", "PID", "UUID"))]
    for v in vms:
        fn, gl = theme.state_style(v.state)
        name = v.name if len(v.name) <= wn else v.name[:wn - 1] + "…"
        rows.append("%s %s %s %s %s %s %s %s %s" % (
            theme.bold(str(v.index).ljust(3)),
            fn(gl),
            fn(name.ljust(wn)),
            fn((v.state or "-").ljust(8)),
            theme.fg(str(v.vcpu if v.vcpu is not None else "-").rjust(4)),
            theme.fg(v.mem_human.rjust(5)),
            theme.muted((v.uptime or "-").ljust(12)),
            theme.accent(str(v.pid or "-").ljust(8)),
            theme.muted(v.uuid)))
    title = "Virtual machines  %s  %s running / %s total" % (
        theme.glyph("dot"), theme.success(running), len(vms))
    return frame(title, rows, theme.secondary)


# --- messages ----------------------------------------------------------------
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
    if snap.get("error"):
        return frame("Live monitoring", [err(snap["error"])], theme.error)
    rates = _net_rates(snap, prev)
    measuring = not prev
    return "\n".join([
        _host_panel(snap, spin),
        _vm_panel(agg),
        _net_panel(snap, rates, tapmap, measuring),
        _storage_panel(snap),
    ])


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
