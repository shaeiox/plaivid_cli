"""Host monitoring: pull cluster/node status and resource usage.

Uses ``sball/show`` (cheap, always available) for live CPU/RAM/load, and
``monitoring/system`` for host identity. Returns a plain dict so the renderer
stays dumb; any field that cannot be read is simply left out.
"""

import datetime
import time

from . import transport


def _pct(used, total):
    try:
        return 100.0 * float(used) / float(total)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _uptime_details():
    """Return host/sballd uptime seconds when local Linux exposes them."""
    try:
        with open("/proc/uptime") as uptime_file:
            host_seconds = int(float(uptime_file.read().split()[0]))
    except (OSError, ValueError, IndexError):
        return {}
    result = {"host_uptime_seconds": host_seconds}
    active = transport.systemd_property(
        "sballd", "ActiveEnterTimestampMonotonic", timeout=2)
    try:
        active_seconds = int(active) / 1000000.0
        service_seconds = max(0, int(host_seconds - active_seconds))
        result["sballd_uptime_seconds"] = service_seconds
    except (TypeError, ValueError):
        pass
    return result


def host_status(token):
    """Return a dict of host facts, or {'error': msg} on failure."""
    try:
        resp = transport.sbell("sball", "show", token=token)
    except transport.TransportError as exc:
        return {"error": str(exc)}
    if not resp.ok or resp.description is None:
        return {"error": resp.error_text() if not resp.ok else "no data"}

    # description wraps the payload in <sball-config>; find the node anywhere.
    node = resp.description.find(".//cluster/node")
    if node is None:
        return {"error": "no node data"}
    ru = node.find("resource-usage")
    info = {}
    info["name"] = node.findtext("name") or "?"
    info["ip"] = node.findtext("ip") or ""
    info["sball_state"] = node.findtext("sball-state") or ""
    info["node_state"] = node.findtext("node-state") or ""

    if ru is not None:
        info["version"] = ru.findtext("release_info/version") or ""
        info["host_time"] = ru.findtext("host_time") or ""
        cpus = ru.findall("cpus/cpu")
        if cpus:
            vals = []
            for c in cpus:
                try:
                    vals.append(float(c.text))
                except (TypeError, ValueError):
                    pass
            if vals:
                info["cpu_count"] = len(cpus)
                info["cpu_pct"] = sum(vals) / len(vals)
        used = ru.findtext("ram/used")
        total = ru.findtext("ram/total")
        info["ram_pct"] = _pct(used, total)
        info["ram_used_gb"] = _to_gb(used)
        info["ram_total_gb"] = _to_gb(total)
        info["load1"] = ru.findtext("load-average/_1_minute") or ""
        info["load5"] = ru.findtext("load-average/_5_minutes") or ""
        info["load15"] = ru.findtext("load-average/_15_minutes") or ""
        st = ru.find("main-storage")
        if st is not None:
            tot = st.findtext("total_size")
            avail = st.findtext("available_size")
            info["store_total_gb"] = _to_gb(tot)
            info["store_used_pct"] = _pct(
                (float(tot) - float(avail)) if tot and avail else None, tot)
    info.update(_uptime_details())
    return info


def _to_gb(v):
    try:
        return float(v) / (1024.0 ** 3)
    except (TypeError, ValueError):
        return None


def _f(e, path, default=0.0):
    try:
        return float(e.findtext(path))
    except (TypeError, ValueError, AttributeError):
        return default


def metrics_snapshot(token):
    """A point-in-time snapshot for the live overview.

    Returns raw counters (not rates) plus a timestamp; the caller diffs two
    snapshots to derive network throughput. Network byte counters are keyed by
    interface name so VM taps can be matched back to VMs via vms.tap_map().
    """
    snap = {"ts": time.time(), "net": {}, "storage": []}
    try:
        resp = transport.sbell("monitoring", "metrics", token=token)
    except transport.TransportError as exc:
        return {"error": str(exc)}
    if not resp.ok or resp.description is None:
        return {"error": resp.error_text() if not resp.ok else "no data"}
    m = resp.description.find(".//metrics")
    if m is None:
        return {"error": "no metrics"}

    snap["cpu_pct"] = _f(m, "cpu_info/cpu_usage/total_usage")
    snap["logical_cores"] = int(_f(m, "cpu_info/logical_cores"))
    snap["physical_cores"] = int(_f(m, "cpu_info/physical_cores"))

    vm_ = m.find("memory_info/virtual_memory")
    if vm_ is not None:
        snap["mem_pct"] = _f(vm_, "used_percent")
        snap["mem_used_gb"] = _to_gb(vm_.findtext("used"))
        snap["mem_total_gb"] = _to_gb(vm_.findtext("total"))

    sw = m.find("memory_info/swap_memory")
    if sw is not None:
        snap["swap_pct"] = _f(sw, "used_percent")
        snap["swap_used_gb"] = _to_gb(sw.findtext("used"))
        snap["swap_total_gb"] = _to_gb(sw.findtext("total"))

    si = m.find("system_info")
    if si is not None:
        snap["hostname"] = si.findtext("host_name") or ""
        snap["uptime_human"] = si.findtext("uptime_human") or ""
        snap["os_version"] = ("%s %s" % (si.findtext("platform") or "",
                                         si.findtext("platform_version") or "")).strip()

    # network interfaces (keep type + state so physical uplinks and VM taps
    # can be told apart; loopback excluded)
    for it in m.findall("network_info/interface_list/interface"):
        typ = it.findtext("iface_type") or ""
        if typ == "loopback":
            continue
        name = (it.findtext("name") or "").strip()
        snap["net"][name] = {
            "rx": _f(it, "bytes_recv"), "tx": _f(it, "bytes_sent"),
            "type": typ.strip(), "state": (it.findtext("state") or "").strip()}

    # ALL real filesystems, categorized (pseudo filesystems excluded)
    real_fs = ("ext2", "ext3", "ext4", "xfs", "btrfs", "vfat", "zfs",
               "nfs", "nfs4")
    for dp in m.findall("disk_info/disk_partition_list/disk_partition"):
        fs = dp.findtext("fstype") or ""
        total = _f(dp, "total_bytes")
        if fs not in real_fs or total <= 0:
            continue
        mp = dp.findtext("mountpoint") or ""
        if mp.startswith("/DataStore"):
            kind = "DataStore"
        elif "VirtualFlash" in mp or "FlashMount" in mp:
            kind = "Flash"
        elif mp in ("/", "/boot"):
            kind = "System"
        else:
            kind = "Other"
        snap["storage"].append({
            "mount": mp, "fstype": fs, "total_gb": total / 1e9,
            "used_gb": _f(dp, "used_bytes") / 1e9,
            "pct": _f(dp, "used_percent"), "kind": kind})
    order = {"DataStore": 0, "Flash": 1, "System": 2, "Other": 3}
    snap["storage"].sort(key=lambda s: (order.get(s["kind"], 9), -s["total_gb"]))

    # load average + PVM/cluster facts come from sball/show (not in metrics)
    try:
        host = host_status(token)
        snap["load1"] = float(host.get("load1") or 0)
        snap["load5"] = float(host.get("load5") or 0)
        snap["load15"] = float(host.get("load15") or 0)
        snap["pvm_version"] = host.get("version") or ""
        snap["sball_state"] = host.get("sball_state") or ""
        snap["host_uptime_seconds"] = host.get("host_uptime_seconds")
        snap["sballd_uptime_seconds"] = host.get("sballd_uptime_seconds")
        if not snap.get("hostname"):
            snap["hostname"] = host.get("name") or ""
    except (transport.TransportError, ValueError):
        snap["load1"] = snap["load5"] = snap["load15"] = 0.0
    return snap


def license_info(token):
    """License status + days until expiry, or {} on failure."""
    try:
        resp = transport.sbell("license", "show", token=token)
    except transport.TransportError:
        return {}
    if not resp.ok or resp.description is None:
        return {}
    o = resp.description.find(".//pvm_lcn_obj")
    if o is None:
        return {}
    expire = o.findtext("expire_date") or ""
    days = None
    try:
        d = datetime.datetime.strptime(expire, "%Y/%m/%d").date()
        days = (d - datetime.date.today()).days
    except ValueError:
        pass
    return {"status": o.findtext("license_status") or "",
            "type": o.findtext("license_type") or "",
            "expire": expire, "days_left": days}


def health_report(snap, agg, lic, host):
    """Build a health/capacity report: a verdict + a list of checks.

    Each check is {name, level (ok|warn|crit), detail}. Pure computation over
    data already gathered, so it makes no calls of its own.
    """
    checks = []

    def add(name, level, detail):
        checks.append({"name": name, "level": level, "detail": detail})

    def band(v, warn, crit):
        return "crit" if v >= crit else "warn" if v >= warn else "ok"

    ss = (host or {}).get("sball_state") or snap.get("sball_state") or ""
    add("Cluster quorum", "ok" if ss == "quorate" else "crit",
        "sball state: %s" % (ss or "unknown"))

    worst = None
    for st in snap.get("storage", []):
        if worst is None or st["pct"] > worst["pct"]:
            worst = st
    if worst:
        add("Storage pressure", band(worst["pct"], 80, 90),
            "%s %.0f%% full (%s)" % (worst["kind"], worst["pct"], worst["mount"]))

    cpu = snap.get("cpu_pct") or 0
    add("CPU load", band(cpu, 70, 90), "%.0f%% now" % cpu)
    mem = snap.get("mem_pct") or 0
    add("Memory", band(mem, 80, 90), "%.0f%% used" % mem)

    cores = snap.get("logical_cores") or 0
    if cores and agg:
        ratio = agg["vcpu_total"] / float(cores)
        add("vCPU overcommit", band(ratio, 2.0, 4.0),
            "%d vCPU allocated / %d cores = %.1fx" % (agg["vcpu_total"], cores, ratio))
    tot_gb = snap.get("mem_total_gb") or 0
    if tot_gb and agg:
        alloc_gb = agg["mem_total_mb"] / 1024.0
        run_gb = agg["mem_run_mb"] / 1024.0
        add("RAM overcommit", band(alloc_gb / tot_gb, 1.0, 1.5),
            "%.0f GB allocated / %.0f GB host (%.0f GB running)"
            % (alloc_gb, tot_gb, run_gb))

    if lic:
        dl = lic.get("days_left")
        if lic.get("status") != "verified":
            lvl = "crit"
        elif dl is not None and dl < 30:
            lvl = "warn"
        else:
            lvl = "ok"
        det = lic.get("status") or "?"
        if lic.get("expire"):
            det += ", expires %s" % lic["expire"]
            if dl is not None:
                det += " (%d days)" % dl
        add("License", lvl, det)

    verdict = "ok"
    if any(c["level"] == "crit" for c in checks):
        verdict = "crit"
    elif any(c["level"] == "warn" for c in checks):
        verdict = "warn"
    return {"verdict": verdict, "checks": checks}
