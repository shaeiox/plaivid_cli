# ADR 0002 — Model-independent `docs/brain/` as the agent entry point

- **Status:** Implemented, documented 2026-11-08 as part of the "Model-Agnostic AI Codebase
  Brain" task. **Newly documented decision**, not a historical owner ADR.
- **Date:** 2026-11-08 (current local date; also the date of commit `89fe3d0`).
- **Decision owner:** the task requester for this knowledge-base work; no separate approval
  record exists.
- **Evidence:** `AGENTS.md`, `docs/brain/README.md`, `docs/brain/maintenance/DOCUMENTATION_POLICY.md`,
  `scripts/validate_brain.py`, `.agents/skills/`, existing docs preserved in place.

## Context

Future AI coding agents (Claude Code, Codex, Cursor, GPT-based tools, and others) need to
understand this repository's architecture, locate canonical implementations, and avoid the
retired `plaivid_cli/legacy/` tree without reading every source file. Earlier documentation is
valuable but partly stale and spread across `README.md`, `docs/`, `docs/architecture/adr/`, and
`openspec/`. No root-level agent instruction file existed.

## Decision

1. Create `AGENTS.md` as a concise, vendor-neutral mandatory entry point that directs agents to
   `docs/brain/` and defines an 11-step exploration workflow.
2. Keep all architecture knowledge, repository maps, indexes, contracts, workflows, decisions,
   policies, and Mermaid diagrams under `docs/brain/`. Preserve existing documentation rather
   than replacing it; link to it instead of duplicating it.
3. Provide six portable, model-independent skills under `.agents/skills/` that reference
   `docs/brain/` and document how to invoke them explicitly from `AGENTS.md` (no assumption that
   a platform auto-discovers the directory).
4. Add a read-only, stdlib-only drift validator (`scripts/validate_brain.py`) and document the
   audit workflow; documentation is navigation, not an unquestionable source of truth.
5. Keep the system Git-friendly: plain Markdown + Mermaid; no vector database, embedding
   service, external infrastructure, or new runtime dependency.

## Alternatives

- **Duplicating architecture into `CLAUDE.md` / tool-specific files:** rejected — no such files
  existed and this would couple the knowledge base to a vendor.
- **Auto-generated docs from code only:** rejected as the sole mechanism because existing
  documentation and OpenSpec/ADR history carry intent that static analysis cannot recover.
- **External knowledge service:** explicitly out of scope per the task constraints.
- **Rewriting existing docs:** rejected; discrepancies are recorded in
  [`../../maintenance/DOCUMENTATION_AUDIT.md`](../../maintenance/DOCUMENTATION_AUDIT.md).

## Consequences

- Agents must start with `AGENTS.md` → `docs/brain/README.md`, identify canonical files via
  `MODULE_INDEX.md` / `FEATURE_TO_FILE_MAP.md`, and update affected brain docs after changes.
- Documentation drift becomes detectable with one command; the audit has no write side effects.
- `docs/brain/` must stay synchronized with source changes; the
  [`documentation-maintenance`](../../../../.agents/skills/documentation-maintenance/SKILL.md)
  and [`documentation-audit`](../../../../.agents/skills/documentation-audit/SKILL.md) skills
  define that work.
- Application source code is deliberately untouched by this decision.

## Related modules / documents

`AGENTS.md`, `docs/brain/`, `scripts/validate_brain.py`, `.agents/skills/`,
[`README.md`](README.md), [`../../maintenance/DOCUMENTATION_POLICY.md`](../../maintenance/DOCUMENTATION_POLICY.md),
[`../../maintenance/DOCUMENTATION_AUDIT.md`](../../maintenance/DOCUMENTATION_AUDIT.md).
