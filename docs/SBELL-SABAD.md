# sbell & sabad - PVM Control Protocol Reference

A complete, implementation-level reference for talking to the PVM core daemon
(`sballd`) through either `sbell` (local CLI) or `sabad` (HTTP API). It is
written so that a future developer or AI can send any request correctly and
extend the system. All facts here were verified against PVM **7.1.26** on host
`sponge` (spongebob).

Companion docs: [`ARCHITECTURE.md`](ARCHITECTURE.md) (how this app uses the
protocol), [`REFERENCE.md`](REFERENCE.md) (quick cheat-sheet).

---

## 1. The big picture

`sballd` is the core daemon. Every operation - from listing VMs to stopping one
- is a **command** addressed to a **module**, carrying an **XML parameter
body**, authenticated by a **session token**. There are two ways to reach it:

```
sbell  (local CLI, root)  ──UNIX socket / framed XML──┐
                                                      ├──> sballd  (:7090)
sabad  (HTTP API)  <── nginx /sabad-plaivid ──────────┘
   ^ the Flutter web UI uses this one
```

- **`sbell`** - a binary at `/usr/bin/sbell`. Simplest for on-host automation.
  Requires root (the socket is root-only).
- **`sabad`** - the "Avid Cloud Web API" daemon, HTTP on `127.0.0.1:9999`,
  fronted by nginx at `https://<host>/sabad-plaivid/`. Use for remote/scripted
  access. Needs the right multipart request shape (section 8).

Both ultimately execute the **same commands** with the **same params** and
return the **same XML envelope**.

---

## 2. sbell: invocation

```bash
sbell <module> <command> "<params-xml>" ["<token>"]
```

- Runs as **root** - the sballd UNIX socket is root-only. A non-root call
  returns `errno 108` ("Couldn't connect to UNIX socket ... Permission
  denied"). Use `sudo sbell ...`.
- `<params-xml>` is a single argument (quote it).
- `<token>` is omitted only for `user/login`.

Example:

```bash
sudo sbell vm stop "<vm_key>481e458c-c6ba-4fe7-88f6-26a59e416568</vm_key>" "$TOKEN"
```

`/usr/bin/easyshell` is a shipped bash wrapper that shows canonical param
shapes for common VM operations; `/usr/sbin/pvm-ova` (Python) shows `object/add`
usage. Both are good ground-truth sources when adding commands.

---

## 3. The request/response model

### Response envelope (identical for sbell and sabad)

```xml
<response>
  <status>success|failed</status>
  <action_id>UUID</action_id>
  <description> ...payload... </description>
</response>
```

- **Success**: `<description>` holds the result - either text (e.g. the login
  token) or nested XML (e.g. `<cluster_status>`, `<sball-config>`, `<objects>`).
- **Failure**: `<description>` holds `<mid>MODULE</mid><aid/><errno>N</errno>
  <what>message</what>`. `mid` is the module that rejected it (`actrepo` is the
  authorization/action-repository layer; `user`, `vm`, etc. are specific
  modules).

### Error numbers

| errno | `what` | Meaning / fix |
| --- | --- | --- |
| 39 | UnAuthorized | No/invalid session. Log in; pass the token. |
| 40 | Permission denied | **Usually a malformed params body** (no key parsed) rather than a real rights issue. Re-check the params shape. |
| 106 | Bad module name | Wrong `<module>`. |
| 107 | Bad command name | Wrong `<command>` for that module. |
| 108 | UNIX socket ... Permission denied | sbell not run as root. |
| 137 | Username/Password is not correct | Bad login credentials. |
| 146 | VM '<name>' is ... | VM-state error (e.g. start on a running VM). From `mid=vm`, not actrepo. |
| 185 | sessions exceeds the threshold | Session cap hit. Evict one and retry (section 6). |

> **Critical gotcha:** errno 40 "Permission denied" is returned *before* object
> resolution when sballd cannot extract the expected key from `params`. So a
> wrong params shape looks exactly like an authorization failure. When an
> authorized user gets errno 40 on a well-formed-looking call, suspect the
> params XML shape first.

---

## 4. The params XML rule (most important section)

**Each command defines its own root element - it is NOT always `<params>`.**
The element sballd expects depends on the command. Getting this wrong is the
single most common cause of failure.

| Command | params body |
| --- | --- |
| `user/login` | `<params><username>U</username><password>P</password></params>` |
| `user/logout` | `<params/>` |
| `user/whoami` | `<params/>` |
| `user/objects` | `<params><query>XPATH</query></params>` |
| `user/list-current-user-sessions` | `<params><username>U</username><password>P</password></params>` |
| `vm/stop` | `<vm_key>UUID</vm_key>` (bare, **no** `<params>`) |
| `vm/kill` | `<vm_key>UUID</vm_key>` |
| `vm/reset` | `<vm_key>UUID</vm_key>` |
| `vm/pause` | `<vm_key>UUID</vm_key>` |
| `vm/resume` | `<vm_key>UUID</vm_key>` |
| `vm/screenshot` | `<params><vm_key>UUID</vm_key></params>` (this one *does* use `<params>`) |
| `vm/start` | `<vm_start>...</vm_start>` (see below) |
| `sball/show` | `<params/>` |
| `monitoring/system`, `monitoring/metrics` | `<params/>` |
| `object/add` | `<object_section><pvm_..._obj>...</pvm_..._obj></object_section>` |

`vm/start` full body:

```xml
<vm_start>
  <vm_key>UUID</vm_key>
  <host>auto</host>
  <version_start><version_enable>no</version_enable><version_vkey></version_vkey></version_start>
  <exit_from_replicate>yes</exit_from_replicate>
</vm_start>
```

**How to find a command's params shape** (methodology for future work):

1. `/usr/bin/easyshell` and `/usr/sbin/pvm-ova` on the host show real calls.
2. The Flutter app's compiled JS, `/var/www/html/plaivid/main.dart.js`, builds
   every request. Search it for the route string (e.g. `"vm/stop"`) and for
   where the params are assembled (search for the XML tag, e.g. `<vm_key>`,
   `<vm_start>`). Routes are registered as `A.c7("module/command")`.
3. Capture a real request from the browser dev-tools (the Network tab shows the
   exact multipart body).

---

## 5. Authentication

### Login

```bash
sbell user login "<params><username>manage</username><password>SECRET</password></params>"
```

Success `<description>` is the **token** (a JWT: `base64url(header).base64url(payload).sig`).
Decode the payload for identity only:

```json
{"id":637443,"dmn":"","usr":"manage","exp":"...","tty":"","hst":"","ipa":"127.0.0.1"}
```

- `dmn` (domain) is empty for `manage` and that is normal - permissions are
  resolved server-side by user id, not from this field.
- Pass the token as the **trailing argument** of every later sbell call, or (for
  sabad) as the `token` **cookie**.

### Logout / identity

- `user/logout` with `<params/>` + token.
- `user/whoami` with `<params/>` + token - returns the caller's `pvm_um_obj`.
  Useful as a cheap "is my token still valid?" check.

### Session cap (errno 185) and eviction

There is a per-user limit on concurrent sessions (~10). When reached, `login`
returns errno 185. Recovery (what the web UI and this app do):

1. List the user's sessions - **no token needed**:
   ```bash
   sbell user list-current-user-sessions "<params><username>manage</username><password>SECRET</password></params>"
   ```
   The result's `<description><pvm_session_list>` contains one `<pvm_um_obj>`
   per session; each session's identifier is that element's direct `<uuid>`.
2. Re-login, adding a `<session_delete_uuid>` to evict one as the new one is
   created:
   ```xml
   <params><username>U</username><password>P</password>
     <session_delete_uuid>SESSION-UUID</session_delete_uuid></params>
   ```

> Be mindful of session churn: every `login` consumes a session slot. Always
> `logout` tokens you no longer need, especially in loops/tests.

---

## 6. Command catalog

97 commands across 30 modules. The complete module/command list is in
[`REFERENCE.md`](REFERENCE.md#command-catalog). The ones this app uses:

- **VM power**: `vm/start`, `vm/stop`, `vm/kill`, `vm/reset`, `vm/pause`,
  `vm/resume` (params in section 4).
- **Inventory**: `user/objects` (section 7), `pvm-running-vms` (a separate host
  binary, section 7).
- **Host**: `sball/show`, `monitoring/system`, `monitoring/metrics` (section 7).
- **Introspection** (not yet used, useful for growth): `module/list`,
  `module/object-type-list`, `job/get-object-actions` (returns the actions
  currently valid for a given object - ideal for state-aware menus).

---

## 7. Object model & data queries

### Listing VMs - `user/objects`

`user/objects` runs an XPath-style query over the object store, scoped to what
the session can see:

```xml
<params><query>/objects/object/pvm_vmm_obj[type[text()='pvm_vmm_virtual_machine']]</query></params>
```

(Objects are typed wrappers; the admin query is
`pvm_um_obj[type[text()='pvm_um_admin']]`, etc.)

The result is `<description><sball-config>...<objects><pvm_vmm_obj>...` - iterate
all `pvm_vmm_obj`. Relevant fields per VM:

| Field (relative to `pvm_vmm_obj`) | Meaning |
| --- | --- |
| `uuid` | the VM's UUID = its `vm_key` |
| `name` | display name |
| `description` | free text |
| `virtual_machine/cluster/cluster_status/status` | **state**: `started`, `stopped`, or `off` |
| `virtual_machine/cluster/host` | node id it runs/belongs on |
| `virtual_machine/hardware/cpu/vcpu` | has `<socket>`,`<core>`,`<thread>`; **vCPU = socket x core x thread** |
| `virtual_machine/hardware/memory/size` | RAM in **MB** |
| `virtual_machine/hardware/console/port` | SPICE/VNC console port |

State semantics: `started` = running, `stopped` = defined but powered down,
`off` = defined, not enabled/booted. (A running VM's live PID/uptime is not in
this object - get it from `pvm-running-vms`.)

### Running VMs - `pvm-running-vms`

A host binary (read-only, **no auth**, no root needed). Prints a table:

```
ROW  PID      UPTIME       PORT  VCPU  MEMORY  UUID                                  NAME
3    3287792  8-08:18:27   6047  4     8192    481e458c-c6ba-4fe7-88f6-26a59e416568  Hadi-New
```

Parse columns: `PID UPTIME PORT VCPU MEMORY(MB) UUID NAME`. This is the fast
path for "what's running" and for **automatic UUID discovery** by name.

### Host status - `sball/show`

Returns `<description><sball-config><cluster><node>...`. Under
`node/resource-usage`:

- `release_info/version`, `host_time`, `uptime`
- `cpus/cpu` - a list of per-core usage percentages (average them for total)
- `ram/used`, `ram/total` (bytes)
- `load-average/_1_minute`
- `main-storage/total_size`, `main-storage/available_size` (bytes)

`monitoring/system` adds host identity (hostname, OS, platform, kernel) and
`monitoring/metrics` adds detailed per-core / memory metrics - both under
`<cluster_..._list>` wrappers.

### Creating / deleting objects

There is **no** per-type "create vm" command. New VMs, disks, bridges, etc. are
created with `object/add` carrying an
`<object_section><pvm_..._obj>...</pvm_..._obj></object_section>` body, deleted
with `object/delete`, and partially edited with `object/section-modify`.
`/usr/sbin/pvm-ova` is the reference for building these bodies.

---

## 8. sabad HTTP API

The transport the Flutter web UI uses. Same commands/params, wrapped in HTTP.

### URL & routing

```
POST https://<host>/sabad-plaivid/<module>/<command>
```

nginx (`/opt/pvm/nginx/conf.d/sabad.conf`) proxies `/sabad-plaivid/` (and
`/sabad-inad`, `/sabad-fylad`, `/sabad-rakaard`) to the `sabad` upstream,
injecting a `Product:` header per product.

### Request shape (easy to get wrong)

- `Content-Type: multipart/form-data` with **three** form fields:
  - `version` = `1.0.0`
  - `query` = (empty)
  - `params` = the **action XML** (same body as sbell - bare `<vm_key>` for
    stop, `<vm_start>` for start, etc.; **not** wrapped in `<params>` except
    where section 4 says so).
- Header `Product: Plaivid`.
- The session `token` as a **cookie** (set by the `user/login` response).

> A wrong content-type or an extra `<params>` wrapper makes sabad parse out no
> key, yielding the same misleading `errno 40 Permission denied`.

**Login is the exception**: it works url-encoded with the `<params>` wrapper and
returns the token both in the body `<description>` and as a `token` cookie.

### Worked example (curl)

```bash
base=https://127.0.0.1/sabad-plaivid
VM=481e458c-c6ba-4fe7-88f6-26a59e416568

# login -> token cookie
curl -sk -c cj.txt -X POST "$base/user/login" \
  --data 'params=<params><username>manage</username><password>PASS</password></params>' \
  -H 'Product: Plaivid'

# stop (multipart, bare <vm_key>; --form-string so '<' is not read as a file)
curl -sk -b cj.txt -X POST "$base/vm/stop" \
  --form-string 'version=1.0.0' --form-string 'query=' \
  --form-string "params=<vm_key>$VM</vm_key>" -H 'Product: Plaivid'

# start (multipart, full <vm_start>)
curl -sk -b cj.txt -X POST "$base/vm/start" \
  --form-string 'version=1.0.0' --form-string 'query=' \
  --form-string "params=<vm_start><vm_key>$VM</vm_key><host>auto</host><version_start><version_enable>no</version_enable><version_vkey></version_vkey></version_start><exit_from_replicate>yes</exit_from_replicate></vm_start>" \
  -H 'Product: Plaivid'
```

Responses are the same `<response>` XML envelope as sbell. CORS is configured
(`Access-Control-Allow-Credentials: true`) for the web origin.

---

## 9. The sballd wire protocol (for a native client)

If you want to skip both `sbell` and `sabad` and talk to `sballd` directly
(UNIX socket, or TCP `127.0.0.1:7090`), the framing is:

```
<15-digit zero-padded decimal length><XML>
```

i.e. send `"%015d" % len(xml)` followed by the XML bytes; read the reply the
same way (a 15-byte length prefix, then that many bytes of XML). The login
request at the raw level looks like:

```xml
<request><token></token><module_id>3</module_id><command_id>0</command_id>
  <parameter><params><username>U</username><password>P</password></params></parameter></request>
```

Modules/commands can be addressed by numeric id (`module_id`/`command_id`) or by
name (`module_name`/`command_name`). `sbell` and `sabad` both build this frame
for you - prefer them unless you specifically need an in-process client.

---

## 10. Host tools & file locations (ground truth)

| Path | What it is |
| --- | --- |
| `/usr/bin/sbell` | the CLI client (root) |
| `/usr/bin/easyshell` | bash wrapper showing canonical VM param shapes |
| `/usr/sbin/pvm-running-vms` | running-VM lister (read-only) |
| `/usr/sbin/pvm-ova`, `/usr/bin/execute_job` | reference callers |
| `/var/www/html/plaivid/main.dart.js` | the Flutter UI - authoritative source of every route + params |
| `/opt/pvm/nginx/conf.d/sabad.conf` | the API routing (product prefixes) |
| `/var/lib/pvm/*.xml` | the sballd object store (VMs, users, sessions, networks) |
| `/var/run/pvm/<uuid>.pvmon` | each running VM's QMP control socket (root-only) |
| `/var/log/pvm/messages` | sballd action log - every command start/finish with user, IP, result |
| `:7090` / `:9999` / `:8181` | sballd / sabad / pvm-engine listeners |

The action log is the best way to confirm what a real request did: grep it for
the command name or a VM uuid.

---

## 11. Safety notes for future development

- **Destructive operations** (`vm/stop`, `vm/kill`, `vm/reset`, `object/delete`,
  `sball/node-power-off`) change real infrastructure. Gate them behind explicit
  confirmation, as this app does.
- **Never log tokens or passwords.** The token grants full session access; the
  JWT payload is fine to show, the signature is not.
- **Mind session slots** - log out tokens; use the 185 recovery rather than
  spamming logins.
- **Params first, auth second** when debugging errno 40: validate the XML shape
  against section 4 before assuming a permissions problem.
- When in doubt about any command, read `main.dart.js` and the host wrappers -
  they are the source of truth for this exact PVM version.
