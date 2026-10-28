"""VM inventory: list all VMs, enrich running ones, and resolve selectors.

Two data sources are merged:
  * ``user/objects`` typed query -> every defined VM with uuid, name, state,
    vcpu and memory (the authoritative inventory).
  * ``pvm-running-vms`` -> live PID / uptime / console port for running VMs,
    and the automatic uuid discovery the requirements ask for.
"""

import os
import re

from . import transport

# The query the Plaivid web UI itself uses for the VM list.
VM_QUERY = ("<params><query>/objects/object/pvm_vmm_obj"
            "[type[text()='pvm_vmm_virtual_machine']]</query></params>")


class VM(object):
    def __init__(self, uuid, name):
        self.uuid = uuid
        self.name = name
        self.state = "unknown"   # started | stopped | off | unknown
        self.vcpu = None
        self.mem_mb = None
        self.description = ""
        # live fields (only for running VMs)
        self.pid = None
        self.uptime = None
        self.port = None
        self.index = None        # 1-based position shown in the UI

    @property
    def running(self):
        return self.state in ("started", "running")

    @property
    def mem_human(self):
        if self.mem_mb is None:
            return "-"
        if self.mem_mb >= 1024:
            return "%.0fG" % (self.mem_mb / 1024.0)
        return "%dM" % self.mem_mb


def _vcpu_count(hw_cpu):
    if hw_cpu is None:
        return None
    v = hw_cpu.find("vcpu")
    if v is None:
        return None
    try:
        n = 1
        for tag in ("socket", "core", "thread"):
            val = v.findtext(tag)
            if val:
                n *= int(val)
        return n
    except (TypeError, ValueError):
        return None


def list_all(token):
    """Every defined VM, from the object store. Raises TransportError."""
    resp = transport.sbell("user", "objects", VM_QUERY, token=token)
    if not resp.ok:
        raise transport.TransportError(resp.error_text())
    out = []
    if resp.description is None:
        return out
    for obj in resp.description.iter("pvm_vmm_obj"):
        uuid = obj.findtext("uuid") or ""
        name = obj.findtext("name") or uuid
        vm = VM(uuid, name)
        vm.description = (obj.findtext("description") or "").strip()
        machine = obj.find("virtual_machine")
        if machine is not None:
            vm.state = machine.findtext("cluster/cluster_status/status") \
                or "unknown"
            vm.vcpu = _vcpu_count(machine.find("hardware/cpu"))
            # configured console (SPICE) port; a running VM's live port from
            # pvm-running-vms overrides this during enrichment
            vm.port = machine.findtext("hardware/console/port") or None
            mem = machine.findtext("hardware/memory/size")
            try:
                vm.mem_mb = int(mem) if mem else None
            except ValueError:
                vm.mem_mb = None
        out.append(vm)
    return out


_ROW = re.compile(r"^\s*\d+\s+(\d+)\s+(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+"
                  r"([0-9a-fA-F-]{36})\s+(.+?)\s*$")


def list_running():
    """Running VMs from pvm-running-vms (no auth). Returns list of dicts."""
    raw = transport.running_vms_raw()
    raw = re.sub(r"\033\[[0-9;]*m", "", raw)  # strip color
    rows = []
    for line in raw.splitlines():
        m = _ROW.match(line)
        if not m:
            continue
        pid, uptime, port, vcpu, mem, uuid, name = m.groups()
        rows.append({"uuid": uuid.lower(), "name": name.strip(),
                     "pid": pid, "uptime": uptime, "port": port,
                     "vcpu": int(vcpu), "mem_mb": int(mem)})
    return rows


def inventory(token):
    """Merged, ordered VM list: running first, then by name. Indexed 1..N."""
    vms = list_all(token)
    by_uuid = dict((v.uuid.lower(), v) for v in vms)

    # The object store's cluster_status is authoritative for VM state. We only
    # ENRICH running VMs with live pid / uptime / port from pvm-running-vms;
    # we never override the state with it (it can be empty or lag behind).
    try:
        for r in list_running():
            vm = by_uuid.get(r["uuid"])
            if vm is None:
                vm = VM(r["uuid"], r["name"])
                vm.vcpu, vm.mem_mb = r["vcpu"], r["mem_mb"]
                vms.append(vm)
                by_uuid[r["uuid"]] = vm
            if not vm.running:
                vm.state = "started"
            vm.pid, vm.uptime, vm.port = r["pid"], r["uptime"], r["port"]
    except transport.TransportError:
        pass  # inventory still usable without live enrichment

    # Fallback: any running VM still without an uptime gets it straight from
    # its qemu process in /proc, so uptime never depends on pvm-running-vms.
    missing = [v for v in vms if v.running and not v.uptime]
    if missing:
        procs = proc_uptimes()
        for v in missing:
            hit = procs.get(v.uuid.lower())
            if hit:
                v.pid, v.uptime = hit

    vms.sort(key=lambda v: (0 if v.running else 1, v.name.lower()))
    for i, vm in enumerate(vms, 1):
        vm.index = i
    return vms


def _uptime_secs(uptime):
    """Parse D-HH:MM:SS / HH:MM:SS / MM:SS into seconds (-1 if unknown)."""
    if not uptime:
        return -1
    try:
        days = 0
        if "-" in uptime:
            d, uptime = uptime.split("-", 1)
            days = int(d)
        parts = [int(p) for p in uptime.split(":")]
        while len(parts) < 3:
            parts.insert(0, 0)
        h, m, s = parts[-3:]
        return days * 86400 + h * 3600 + m * 60 + s
    except ValueError:
        return -1


def _num(value):
    s = str(value or "")
    return int(s) if s.isdigit() else -1


def _default_order(v):
    return (0 if v.running else 1, v.name.lower())


SORT_KEYS = {
    "index": _default_order,
    "name": lambda v: v.name.lower(),
    "state": lambda v: (0 if v.running else 1, v.state or ""),
    "cpu": lambda v: v.vcpu or 0,
    "mem": lambda v: v.mem_mb or 0,
    "uptime": lambda v: _uptime_secs(v.uptime),
    "pid": lambda v: _num(v.pid),
    "port": lambda v: _num(v.port),
    "uuid": lambda v: v.uuid,
}


def sort_vms(vms, key=None, desc=False):
    """Return VMs sorted by ``key`` and re-indexed in display order, so an
    index typed by the user always matches the row they see."""
    out = sorted(vms, key=SORT_KEYS.get(key) or _default_order, reverse=desc)
    for i, vm in enumerate(out, 1):
        vm.index = i
    return out


def _fmt_elapsed(secs):
    """Format seconds like pvm-running-vms: D-HH:MM:SS, HH:MM:SS or MM:SS."""
    secs = int(max(0, secs))
    days, rem = divmod(secs, 86400)
    hours, rem = divmod(rem, 3600)
    mins, sec = divmod(rem, 60)
    if days:
        return "%d-%02d:%02d:%02d" % (days, hours, mins, sec)
    if hours:
        return "%02d:%02d:%02d" % (hours, mins, sec)
    return "%02d:%02d" % (mins, sec)


def proc_uptimes():
    """{uuid: (pid, uptime)} for every qemu process visible in /proc.

    Reads each process's cmdline for ``-uuid <uuid>`` and its start time from
    /proc/<pid>/stat. Returns {} where /proc is unavailable (e.g. Windows).
    """
    found = {}
    try:
        tick = float(os.sysconf("SC_CLK_TCK"))
        with open("/proc/uptime") as fh:
            sys_up = float(fh.read().split()[0])
        pids = [p for p in os.listdir("/proc") if p.isdigit()]
    except (OSError, ValueError, AttributeError):
        return found
    for pid in pids:
        try:
            with open("/proc/%s/cmdline" % pid, "rb") as fh:
                args = fh.read().split(b"\0")
            if b"-uuid" not in args:
                continue
            uuid = args[args.index(b"-uuid") + 1].decode("ascii").lower()
            with open("/proc/%s/stat" % pid) as fh:
                fields = fh.read().rsplit(")", 1)[1].split()
            started = float(fields[19]) / tick   # field 22: starttime (ticks)
            found[uuid] = (pid, _fmt_elapsed(sys_up - started))
        except (OSError, ValueError, IndexError, UnicodeDecodeError):
            continue
    return found


def aggregate(vms):
    """Summarize a VM list: counts by state and allocated vCPU/memory."""
    agg = {"total": len(vms), "running": 0, "stopped": 0, "off": 0,
           "paused": 0, "vcpu_run": 0, "vcpu_total": 0,
           "mem_run_mb": 0, "mem_total_mb": 0}
    for v in vms:
        vc = v.vcpu or 0
        mm = v.mem_mb or 0
        agg["vcpu_total"] += vc
        agg["mem_total_mb"] += mm
        if v.running:
            agg["running"] += 1
            agg["vcpu_run"] += vc
            agg["mem_run_mb"] += mm
        elif v.state == "stopped":
            agg["stopped"] += 1
        elif v.state == "off":
            agg["off"] += 1
        elif v.state == "paused":
            agg["paused"] += 1
    return agg


def detail(token, vm):
    """Fetch and parse the full object for one VM into a structured dict.

    ``vm`` may be a VM instance or a uuid string. Returns a dict grouped for
    the detail renderer; raises TransportError if the VM cannot be read.
    """
    uuid = getattr(vm, "uuid", vm)
    query = ("<params><query>/objects/object/pvm_vmm_obj"
             "[uuid[text()='%s']]</query></params>" % uuid)
    resp = transport.sbell("user", "objects", query, token=token)
    if not resp.ok:
        raise transport.TransportError(resp.error_text())
    obj = resp.description.find(".//pvm_vmm_obj") if resp.description is not None else None
    if obj is None:
        raise transport.TransportError("VM not found: %s" % uuid)
    m = obj.find("virtual_machine")

    def g(path, default=""):
        return (m.findtext(path) if m is not None else None) or default

    sc = [g("hardware/cpu/vcpu/%s" % x, "1") for x in ("socket", "core", "thread")]
    try:
        vcpu = int(sc[0]) * int(sc[1]) * int(sc[2])
    except ValueError:
        vcpu = None

    d = {
        "name": obj.findtext("name") or "",
        "uuid": obj.findtext("uuid") or uuid,
        "description": (obj.findtext("description") or "").strip(),
        "enabled": obj.findtext("is_enabled") or "",
        "ha": obj.findtext("ha_enabled") or "",
        "created": obj.findtext("created_datetime") or "",
        "modified": obj.findtext("modified_datetime") or "",
        "state": g("cluster/cluster_status/status", "unknown"),
        "host": g("cluster/host"),
        "auto_start": g("cluster/auto_start"),
        "always_on": g("cluster/always_on"),
        "qemu": g("cluster/cluster_status/qemu_version"),
        "vcpu": vcpu, "vcpu_topo": "%sx%sx%s" % (sc[0], sc[1], sc[2]),
        "cpu_model": g("hardware/cpu/model"),
        "mem_mb": int(g("hardware/memory/size", "0") or 0),
        "machine": g("hardware/emulated_machine/type"),
        "uefi": g("hardware/bios/uefi"),
        "disks": [], "nics": [], "console": {},
    }
    if m is not None:
        for dk in m.findall("hardware/disk_manager/disk_list/disk"):
            d["disks"].append({
                "name": dk.findtext("name") or "",
                "media": dk.findtext("media") or "",
                "controller": dk.findtext("controller") or "",
                "boot": dk.findtext("boot_index") or "",
                "cache": dk.findtext("cache") or ""})
        for na in m.findall("hardware/net_adaptor_list/net_adaptor"):
            d["nics"].append({
                "name": na.findtext("name") or "",
                "device": na.findtext("device") or "",
                "mac": na.findtext("macaddr") or "",
                "tap": na.findtext("tap_name") or "",
                "enable": na.findtext("enable") or ""})
        c = m.find("hardware/console")
        if c is not None:
            d["console"] = {
                "type": c.findtext("type") or "",
                "port": c.findtext("port") or "",
                "bind": c.findtext("bind_address") or "",
                "password": c.findtext("password_enable") or "",
                "tls": c.findtext("tls") or ""}
    # live fields if we were handed an enriched VM
    d["pid"] = getattr(vm, "pid", None)
    d["uptime"] = getattr(vm, "uptime", None)
    return d


def tap_map(token):
    """Map host tap-interface name -> VM name, for per-VM network stats.

    Each VM's net adaptors carry a ``tap_name`` that equals the interface name
    reported by monitoring/metrics, so this joins the two data sources.
    """
    resp = transport.sbell("user", "objects", VM_QUERY, token=token)
    mapping = {}
    if resp.ok and resp.description is not None:
        for obj in resp.description.iter("pvm_vmm_obj"):
            name = obj.findtext("name") or ""
            for na in obj.iter("net_adaptor"):
                tap = na.findtext("tap_name")
                if tap:
                    mapping[tap] = name
    return mapping


def resolve(vms, selector):
    """Find a VM by 1-based index, exact name, uuid, or unique name prefix."""
    sel = (selector or "").strip()
    if not sel:
        return None, "no VM given"
    if sel.isdigit():
        n = int(sel)
        for vm in vms:
            if vm.index == n:
                return vm, None
        return None, "no VM at index %s" % sel
    low = sel.lower()
    for vm in vms:                                   # exact name / uuid
        if vm.name.lower() == low or vm.uuid.lower() == low:
            return vm, None
    matches = [vm for vm in vms if low in vm.name.lower()]
    if len(matches) == 1:
        return matches[0], None
    if len(matches) > 1:
        names = ", ".join(vm.name for vm in matches[:6])
        return None, "'%s' is ambiguous: %s" % (selector, names)
    return None, "no VM matches '%s'" % selector


def _state_of(vm):
    return "running" if vm.running else (vm.state or "unknown")


def resolve_many(vms, selector):
    """Resolve a selector to a LIST of VMs for bulk actions.

    Supports: ``all``; a state keyword (``running`` / ``stopped`` / ``off`` /
    ``paused``) or ``state:<name>``; a comma-separated list of indexes/names;
    or a single selector (list of one). Returns (list, error_or_None).
    """
    sel = (selector or "").strip()
    low = sel.lower()
    if not sel:
        return [], "no VM given"
    if low == "all":
        return list(vms), None
    if low.startswith("state:"):
        low = low.split(":", 1)[1].strip()
    if low in ("running", "stopped", "off", "paused"):
        matched = [vm for vm in vms if _state_of(vm) == low]
        return matched, (None if matched else "no %s VMs" % low)
    if "," in sel:
        out, errs, seen = [], [], set()
        for tok in sel.split(","):
            tok = tok.strip()
            if not tok:
                continue
            vm, err = resolve(vms, tok)
            if vm and vm.uuid not in seen:
                seen.add(vm.uuid)
                out.append(vm)
            elif err:
                errs.append(err)
        if not out:
            return [], "; ".join(errs) or "no match"
        return out, ("; ".join(errs) if errs else None)
    vm, err = resolve(vms, sel)
    return ([vm] if vm else []), err
