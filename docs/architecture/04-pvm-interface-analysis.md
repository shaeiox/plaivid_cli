# 04 — PVM Interface Analysis

**Audit date:** 2026-10-30  
**Evidence limit:** No PVM host, `sbell` binary, `pvm-running-vms` binary, API endpoint, sample output, or target log was available. Statements are explicitly labeled source-verified, documentation-only, or unknown. No undocumented command is proposed.

## Interface inventory

### Interfaces used by current source

| Interface | Source use | What code expects | Evidence status |
|---|---|---|---|
| `sbell user login` | `session.login()` | XML `<response>`; token text in `<description>`; error fields under description | Source-verified caller/parser: `session.py:80–123`, `transport.py:80–107`. Actual stdout/stderr/exit-code behavior on PVM is unverified. |
| `sbell user whoami` | Cached-session validation | successful response means cached token is usable | Source-verified: `session.py:69–77`; server semantics are documented in `docs/SBELL-SABAD.md:149–174`, not live-tested. |
| `sbell user logout` | Explicit logout | response is invoked but status is ignored | Source-verified: `session.py:126–133`. |
| `sbell user list-current-user-sessions` | errno 185 recovery | parses `pvm_session_list/pvm_um_obj/uuid`, then retries login with first returned UUID | Source-verified: `session.py:88–105, 107–123`; sequence semantics documentation-only. |
| `sbell user objects` | Inventory, detail and tap mapping | XML description with `pvm_vmm_obj`; inventory query wraps a typed XPath-like query in `<params><query>` | Source-verified query/parser: `vms.py:15–17, 64–91, 267–281, 342–357`. Supported query behavior/version compatibility unverified. |
| `pvm-running-vms` | Live VM enrichment | text table parsed by a fixed regular expression into PID, uptime, port, vCPU, memory, UUID, name | Source-verified: `vms.py:94–111`; exact live format and exit behavior unverified. Not structured output. |
| `sbell sball show` | Host status and supplemental metrics | response XML with a path to `.//cluster/node`, node status/resource usage; `sball_state` and `node_state` fields | Source-verified parser: `monitoring.py:21–70`; schema and cluster coverage documentation-only. |
| `sbell monitoring metrics` | Detailed host metrics | XML `.//metrics`, system/memory/CPU/network/storage fields | Source-verified parser: `monitoring.py:87–175`; actual PVM schema/version coverage documentation-only. |
| `sbell license show` | License status in health screen | XML `.//pvm_lcn_obj` and license status/type/expiry | Source-verified parser: `monitoring.py:178–198`; availability/permissions unverified. |
| `sbell vm start/stop/kill/reset/pause/resume` | Six VM operations | XML params, token appended as argument; success/error envelope | Source-verified code: `actions/*.py`, `actions/base.py:27–44`, `transport.py:99–107`; actual policy/semantics documentation-only. |

### Documented interfaces not used by application source

`docs/SBELL-SABAD.md` describes sabad HTTP request framing, raw sballd framing, command examples, and PVM file locations. `docs/REFERENCE.md` documents `monitoring/system`, introspection commands, and a broad sbell command catalog. These are **repository documentation**, not verified target capabilities. No source calls sabad, an HTTP endpoint, raw socket framing, `monitoring/system`, `job/get-object-actions`, or any of the larger documented command catalog.

This analysis does not recommend invoking undocumented endpoints or infer command syntax beyond code/documentation present in the repository.

## Inventory and detail behavior

1. `vms.list_all(token)` issues one `user/objects` request with the VM type query and parses each returned `pvm_vmm_obj` into a VM (`vms.py:64–91`). This is a **batched all-defined-VM object query at the caller level**.
2. `vms.inventory(token)` then separately runs `pvm-running-vms` to enrich running VMs and may add running rows absent from the object list (`vms.py:114–149`). Thus current inventory is not one atomic/batched interface call: it is at least one sbell request plus one local process invocation.
3. `vms.detail(token, vm)` issues a separate `user/objects` query with a UUID predicate and extracts a selected VM's full object (`vms.py:267–339`). Detail is on-demand in current command flow, not included as a follow-up request per VM.
4. `vms.tap_map(token)` issues another all-VM object query to map tap names to VM names (`vms.py:342–357`). Overview makes this call once before its refresh loop.

**Unverified:** Whether one `user/objects` response contains every required inventory field on every supported PVM build, whether query filters/indexing scale, whether permissions hide objects, whether any supported `sbell` mode offers JSON/other structured output, whether `pvm-running-vms` has a stable machine-readable mode, and whether a single command can combine host/cluster/node/VM information.

## Argument, output, error and exit-code handling

- `transport.sbell()` builds argv `[configured command..., module, command, params, optional token]`; `subprocess.Popen` receives a list (no shell requested), stdin is `DEVNULL`, stdout/stderr are pipes, and `communicate()` applies the configured timeout (`transport.py:66–77, 99–107`).
- Password-bearing XML and tokens are passed within argv. This is a confidentiality risk even though no shell is invoked; see `06-security-and-reliability.md`.
- Response output is expected to be a single XML document beginning with `<`; `ElementTree.fromstring()` parses status, action id, description, errno, what and mid (`transport.py:80–96`).
- **Important code fact:** `_run()` returns the child return code, but `sbell()` discards it. It raises only when stdout is empty and stderr non-empty; XML in stdout is parsed regardless of nonzero exit status (`transport.py:99–107`). Thus the application does not establish that sbell exit codes are meaningful or consistently handled.
- For `pvm-running-vms`, a nonzero return code errors only if stdout is empty; non-empty output is accepted (`transport.py:110–115`).
- `TransportError` covers launch, timeout and parse errors; an XML-level failed response is instead represented by `Response.ok == False`. Callers differ in whether they surface, suppress, or map this to an action result.
- No live evidence was collected for errno meanings, stdout/stderr format, action IDs, partial output, process descendants, or timeout behavior.

## Node, Cluster, Membership, Quorum and Health

### What current code can demonstrate

- `monitoring.host_status()` searches for the **first** `.//cluster/node` element and reads that node's name, IP, sball state, node state and resource usage (`monitoring.py:30–70`).
- `monitoring.metrics_snapshot()` parses metrics XML for the local/returned host's CPU, memory, system identity, interfaces and partitions; it then separately calls `sball/show` for load and sball state (`monitoring.py:87–175`).
- `health_report()` labels a check “Cluster quorum” but only considers `sball_state == "quorate"` healthy; it does not parse a membership set, member count, quorum vote count, or per-node health collection (`monitoring.py:201–265`).
- Health thresholds for CPU/RAM/storage/overcommit are literal constants in this function and are not validated by the documents as vendor policy.

### What cannot be established from current code

- A complete cluster membership list, all node identities/statuses, quorum votes/majority, node reachability, and cluster-wide resource aggregation are **not established** by the current parsers.
- A field called `sball_state` equal to `quorate` is not sufficient evidence that the application has enough data to independently verify membership, quorum safety, or each node's health.
- `sball/show` response shape and whether its “cluster” contains more than the local node are undocumented by source; the existing parser deliberately selects one node.
- Repository docs describe PVM node/cluster objects and label some fields, but the actual target schema and semantics need a representative captured response and confirmation from PVM owners.

**Conclusion:** Current code supports a useful local host snapshot and a single status label that it calls quorum. “Cluster-aware, limited to information accessible through local interfaces” is an approved product boundary, not a verified current capability. Define the exact set of local cluster facts available before presenting cluster health as authoritative.

## Required host investigation (read-only, with authorization)

On a controlled supported PVM environment, capture redacted representative outputs and metadata for only the commands already invoked by the application: login/whoami flow as permitted; `user objects` inventory query; `pvm-running-vms`; `sball show`; `monitoring metrics`; `license show`; and a harmless/read-only view of response/exit behavior. Record PVM build, command versions, user permissions, timing, stdout/stderr, exit status and schemas. Do not execute VM-changing actions as part of schema discovery. If a later operation experiment is approved, isolate it to a disposable test VM and obtain explicit authorization.

Also ask the PVM owner/vendor for the supported contract for cluster membership/quorum and version compatibility. Do not infer a new command from a broad command catalog.
