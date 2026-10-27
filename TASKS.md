# Plaivid CLI - Roadmap tasks

Small, independent tasks for the next features. Each is sized to land on its own
branch without touching the others. Checkboxes track progress.

---

## 1. VM detail view (`show <id|name>`)  -  IN PROGRESS (this branch)

A read-only, grouped detail page for a single VM.

- [x] Probe the full `pvm_vmm_obj` schema (disks, NICs, console, bios, cluster).
- [ ] `vms.detail(token, vm)` - query one VM by uuid and parse into a dict.
- [ ] `render.vm_detail(detail)` - grouped containers: General, Compute,
      Disks, Network, Console.
- [ ] `show` / `detail` / `info` command in the orchestrator (interactive +
      one-shot), with Tab completion and help entry.
- [ ] Verify on host; commit.

Acceptance: `show Hadi-New` and `show 12` both render name, uuid, state, host,
HA/boot, vCPU topology, memory, disks, NICs (device/MAC/tap) and the SPICE/VNC
console endpoint.

## 2. Auto-refresh + filter/search in the main VM list

- [ ] `watch` mode for the VM list (reuse the `overview` live-loop pattern:
      cbreak + select, `q` to stop).
- [ ] `filter <text>` / `filter state:running` to narrow the list.
- [ ] A `/` quick-filter in interactive mode; clear with empty filter.

Acceptance: the dashboard can auto-refresh every N seconds and be filtered by
name substring or by state, without leaving the TUI.

## 3. Per-VM action menu (state-aware)

- [ ] Call `job/get-object-actions` for a selected VM to learn the actions
      valid for its current state.
- [ ] `menu <id>` - list only the applicable actions and let the user pick.
- [ ] Fall back to the static `actions/` registry if the call is unavailable.

Acceptance: a stopped VM offers Start (not Stop/Kill); a running VM offers
Stop/Kill/Reset/Pause - driven by the server, not hard-coded.

## 4. Sparklines + alerts in `overview`

- [ ] Keep a short ring-buffer of recent CPU / network / RAM samples.
- [ ] Render unicode sparklines next to each metric.
- [ ] Threshold coloring: warn (yellow) >70%, critical (red) >90% on CPU, RAM,
      load and each storage volume.

Acceptance: the overview shows a small trend line per metric and turns
red when a resource is critically high.

## 5. Audit / log viewer

- [ ] `log` command: show recent entries from `/var/log/pvm/messages`
      (and/or `log/select`), parsed into time / user / action / result.
- [ ] Filter by VM name or user; follow (tail -f) mode.

Acceptance: `log` shows the latest PVM actions with who did what and the
result, newest first.

---

### Conventions
- One feature per branch; keep `actions/` files independent.
- Data access goes through `transport.sbell()`; no new direct subprocess calls.
- Read-only by default; destructive operations require confirmation.
- Verify against a real host before committing.
