# Plaivid CLI & sbell Reference

A practical reference for driving Plaivid / PVM from the command line via
`sbell` (and the equivalent `sabad` HTTP API). Host: `sponge` (spongebob),
PVM 7.1.

> Also published as a living doc: https://claude.ai/artifact/NiSYaLtbRhicHZkFwX2rPE

## Overview & architecture

Plaivid is a Flutter web UI backed by the PVM stack. Everything the UI does is
a command sent to `sballd`, the core daemon; the CLI reaches that same core
through `sbell`.

```
Browser (Flutter UI) --HTTPS--> nginx :443 --/sabad-plaivid--> sabad :9999 --.
                                                                              |
CLI / TUI (root) --------------> sbell (UNIX socket) ------------------------>+--> sballd :7090 --> VMs (qemu, QMP .pvmon)
```

The browser talks HTTPS to nginx, which serves the static UI and proxies API
calls to the `sabad` HTTP service; `sabad` forwards to `sballd`. `sbell` skips
all of that and speaks to sballd's local UNIX socket directly. Both paths
converge on `sballd`, which drives the qemu VMs. So anything the web UI can do,
`sbell` can do too.

## Authentication & sessions

Every action call needs a session token: get one from `user/login`, pass it to
each later call, drop it with `user/logout`.

```bash
# login -> token is returned inside <description>
sbell user login "<params><username>manage</username><password>SECRET</password></params>"
#   -> <response><status>success</status>...<description>eyJ...JWT...</description></response>

sbell vm stop "<vm_key>UUID</vm_key>" "$TOKEN"     # use the token on every call
sbell user logout "$TOKEN"
```

The token is a JWT; its payload carries `id`, `dmn` (domain — empty for
`manage`, which is normal; permissions are resolved server-side by user id),
`usr`, `exp`, and `tty`/`hst`/`ipa`. Login is the only call that takes no token.

**Session cap (errno 185):** there is a per-user limit on concurrent sessions.
List them with `user list-current-user-sessions` (takes username+password, no
token) and evict one by re-logging in with a `<session_delete_uuid>` in the
params. (The CLI does this automatically.)

## How sbell works

```bash
sbell <module> <command> "<params-xml>" ["<token>"]
```

1. **Run as root** — the sballd socket is root-only (`errno 108` otherwise).
2. **Get the params XML shape right** — each action defines its own root
   element; it is NOT always `<params>`. `vm/stop` wants a bare
   `<vm_key>UUID</vm_key>`; `vm/start` wants `<vm_start>...</vm_start>`;
   `user/login` wants `<params>...</params>`. A wrong shape yields a
   *misleading* `errno 40 Permission denied`.
3. **Attach a valid token** (every call except `user/login`).

Response envelope:

```xml
<response>
  <status>success|failed</status>
  <action_id>UUID</action_id>
  <description>...payload, or <mid>module</mid><errno>N</errno><what>message</what>...</description>
</response>
```

| errno | Meaning / fix |
| --- | --- |
| 39 | Unauthorized — no valid session |
| 40 | Permission denied — often a malformed params body, not a real rights issue |
| 106 | Bad module name |
| 107 | Bad command name |
| 108 | Socket permission denied — not running as root |
| 137 | Username/password incorrect |
| 146 | VM-state error (e.g. start on a running VM) |
| 185 | Too many sessions — evict one and retry |

## Command catalog

97 commands across 30 modules. Each is callable as `sbell <module> <command>`
and as `POST /sabad-plaivid/<module>/<command>`.

| Module | Commands |
| --- | --- |
| `user` | login, logout, whoami, objects, change-password, download-profile, update-profile, upload-profile, get-login-history, list-current-user-sessions, ldap-sync-users, ldap-users |
| `vm` | start, stop, kill, reset, pause, resume, screenshot, query-net-quota |
| `object` | add, delete, section-modify |
| `sball` | show, master, get-cpu-info, node-power-on, node-power-off |
| `module` | list, object-type-list |
| `monitoring` | metrics, system |
| `network` | nic-list, list-active-ntp |
| `vnet` | set-traffic-quota |
| `flash` | create, connect, disconnect, unmount, get-access, grant-access, change-owner |
| `storage` | file-upload, scan, scan-backup, usbfs-lsblk, usbfs-mount, usbfs-unmount |
| `usb` | ls-host-usb |
| `container` | create-instance, import-template, reset-quota |
| `desktop` | create-version, remove-version, rebuild, change-group, delete-group, remove-template, sync-group-setting |
| `broker` | run, stop, block, unblock, console, fetch-active-session |
| `job` | task-run, task-cancel, get-object-actions |
| `vmbackup` | delete |
| `vmclone` | run |
| `vmmigrate` | run |
| `vmstrgmigrate` | run |
| `vmreplicate` | get-slave-list |
| `fylad` | create, convert, cleaning, resize-flash, manage-access, query-access-report, query-link, remove-link |
| `fyladbackup` | delete |
| `fyladkiosk` | check-new-version, update-new-version-info |
| `inad` | assign-net-policy, query-net-policy, query-url, query-access-report, delete-unused-flashes |
| `license` | show, system-key, update |
| `log` | select |
| `report` | test-email |
| `talk` | run-command |
| `change` | password |
| `help` | help |

### VM action params (the ones the CLI uses)

- `vm/stop` — `<vm_key>UUID</vm_key>` — graceful ACPI shutdown.
- `vm/kill` — `<vm_key>UUID</vm_key>` — forced power-off.
- `vm/reset` / `vm/pause` / `vm/resume` — `<vm_key>UUID</vm_key>`.
- `vm/start` —
  `<vm_start><vm_key>UUID</vm_key><host>auto</host><version_start><version_enable>no</version_enable><version_vkey></version_vkey></version_start><exit_from_replicate>yes</exit_from_replicate></vm_start>`
- `vm/screenshot` — `<params><vm_key>UUID</vm_key></params>` (this one *does*
  use the `<params>` wrapper).

### Listing VMs

- Running only (no auth): `pvm-running-vms` — gives PID, uptime, port, vCPU,
  memory, **UUID** and name.
- All defined VMs (needs a token): `user objects` with query
  `/objects/object/pvm_vmm_obj[type[text()='pvm_vmm_virtual_machine']]`.
  Each `pvm_vmm_obj` carries `uuid`, `name`, `description`, and under
  `virtual_machine`: `cluster/cluster_status/status` (`started`/`stopped`/`off`),
  `hardware/cpu/vcpu` (socket×core×thread), `hardware/memory/size` (MB).

### Introspection (useful for a TUI)

`module/list`, `module/object-type-list` enumerate modules and object types;
`job/get-object-actions` returns the actions currently valid for an object;
`user/objects` runs XPath-style queries over what your session can see.

## Host CLI tools & layout

| Tool | What it does |
| --- | --- |
| `pvm-running-vms` | lists running VMs (read-only, no login); UUID column is the `vm_key` |
| `/usr/bin/easyshell` | friendly `sbell` wrapper (`vm_list`, `vm_start <key> <host>`, `vm_kill <key>`, `*_list`); run as root |
| `/usr/bin/execute_job` | logs in as the `pvm` user and runs a scheduler task |
| `sabad` | the Web API daemon — HTTP on `127.0.0.1:9999`, behind nginx `/sabad-plaivid/` |
| `pvm` meta-service | `systemctl {start,stop,restart} pvm` manages the whole stack |

| Path | Contents |
| --- | --- |
| `/etc/pvm/engine/*/manager.conf` | per-module engine config |
| `/opt/pvm/nginx/conf.d/` | nginx (`sabad.conf` routes the API) |
| `/var/www/html/plaivid/` | the Flutter web UI (`main.dart.js`) |
| `/var/lib/pvm/*.xml` | the sballd object store |
| `/var/run/pvm/<uuid>.pvmon` | each running VM's QMP control socket (root-only) |
| `/var/log/pvm/messages` | sballd action log |
| `:7090` / `:9999` / `:8181` | sballd / sabad / pvm-engine |

## sbell vs the sabad HTTP API

Same commands, two transports. The HTTP API (what the browser uses) needs a
specific request shape:

- `POST https://<host>/sabad-plaivid/<module>/<command>`
- `Content-Type: multipart/form-data` with **three** fields: `version=1.0.0`,
  `query=` (empty), `params=<action-xml>`.
- Header `Product: Plaivid`; the session `token` as a **cookie**.
- `params` is the **bare action element**, not wrapped in `<params>` (login is
  the exception — it is url-encoded with the `<params>` wrapper).

```bash
base=https://127.0.0.1/sabad-plaivid; VM=<uuid>
curl -sk -c cj.txt -X POST "$base/user/login" \
  --data 'params=<params><username>manage</username><password>PASS</password></params>' \
  -H 'Product: Plaivid'
curl -sk -b cj.txt -X POST "$base/vm/stop" \
  --form-string 'version=1.0.0' --form-string 'query=' \
  --form-string "params=<vm_key>$VM</vm_key>" -H 'Product: Plaivid'
```

On-host with `sbell` (what this CLI uses): no TLS, no cookies, token passed as
the trailing argument — see **How sbell works**.
