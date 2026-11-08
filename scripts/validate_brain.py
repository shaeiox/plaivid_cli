#!/usr/bin/env python3
"""Read-only documentation drift validator for the ``docs/brain/`` knowledge base.

Checks the required documentation tree, Markdown links, referenced repository paths,
``path.py::Symbol`` evidence tokens, feature-to-file mappings, entry points, Mermaid
diagrams, skill definitions, AGENTS.md references, and legacy labels.

This script only reads files. It never writes to the repository and has no dependencies
outside the Python standard library.

Usage:
    python scripts/validate_brain.py
    python scripts/validate_brain.py --verbose
    python scripts/validate_brain.py --dependency-stats

``--dependency-stats`` recomputes the AST-derived numbers quoted in
``docs/brain/architecture/DEPENDENCY_GRAPH.md`` (module counts, fan-in/fan-out, layer
edge counts, legacy boundaries, and strongly connected components).
"""

from __future__ import annotations

import ast
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRAIN = ROOT / "docs" / "brain"
SKILLS_DIR = ROOT / ".agents" / "skills"
PKG = ROOT / "plaivid_cli"

REQUIRED_FILES = (
    "AGENTS.md",
    "docs/brain/README.md",
    "docs/brain/architecture/SYSTEM_OVERVIEW.md",
    "docs/brain/architecture/ARCHITECTURE.md",
    "docs/brain/architecture/COMPONENTS.md",
    "docs/brain/architecture/DATA_FLOW.md",
    "docs/brain/architecture/DEPENDENCY_GRAPH.md",
    "docs/brain/codebase/REPOSITORY_MAP.md",
    "docs/brain/codebase/FILE_CATALOG.md",
    "docs/brain/codebase/MODULE_INDEX.md",
    "docs/brain/codebase/ENTRYPOINTS.md",
    "docs/brain/codebase/FEATURE_TO_FILE_MAP.md",
    "docs/brain/contracts/MODULE_CONTRACTS.md",
    "docs/brain/contracts/API_CONTRACTS.md",
    "docs/brain/contracts/DATA_MODELS.md",
    "docs/brain/workflows/DEVELOPMENT.md",
    "docs/brain/workflows/BUILD.md",
    "docs/brain/workflows/TESTING.md",
    "docs/brain/workflows/RELEASE.md",
    "docs/brain/decisions/ADR/README.md",
    "docs/brain/maintenance/DOCUMENTATION_POLICY.md",
    "docs/brain/maintenance/DOCUMENTATION_AUDIT.md",
    "docs/brain/diagrams/system-context.mmd",
    "docs/brain/diagrams/component-architecture.mmd",
    "docs/brain/diagrams/dependency-overview.mmd",
    ".agents/skills/codebase-exploration/SKILL.md",
    ".agents/skills/architecture-analysis/SKILL.md",
    ".agents/skills/feature-impact-analysis/SKILL.md",
    ".agents/skills/code-navigation/SKILL.md",
    ".agents/skills/documentation-maintenance/SKILL.md",
    ".agents/skills/documentation-audit/SKILL.md",
    "scripts/validate_brain.py",
)

SKILL_NAMES = (
    "codebase-exploration",
    "architecture-analysis",
    "feature-impact-analysis",
    "code-navigation",
    "documentation-maintenance",
    "documentation-audit",
)

SKILL_HEADINGS = (
    "## Purpose",
    "## When to use",
    "## Required knowledge documents",
    "## Step-by-step procedure",
    "## Expected output",
    "## Validation criteria",
)

FEATURE_FIELDS = (
    "- **Description:**",
    "- **Entry point:**",
    "- **Main implementation:**",
    "- **Supporting modules:**",
    "- **Shared dependencies:**",
    "- **Data models:**",
    "- **Tests:**",
    "- **Related contracts:**",
    "- **Potential impact areas:**",
    "- **Files that should NOT be modified:**",
    "- **Documentation references:**",
)

ENTRYPOINT_TOKENS = (
    "plaivid_cli/bootstrap.py::main",
    "plaivid_cli/bootstrap.py::build_runtime",
    "plaivid_cli/presentation/cli/parser.py::build_parser",
    "plaivid_cli/presentation/cli/dispatch.py::run_command",
    "plaivid_cli/presentation/tui/app.py::PlaividTui",
    "setup.py::RuntimeBuildPy",
    "scripts/validate_brain.py::main",
)

PATH_ROOTS = (
    "plaivid_cli/",
    "tests/",
    "docs/",
    "scripts/",
    ".agents/",
    "openspec/",
    "assets/",
)
PATH_FILES = frozenset(
    {
        "AGENTS.md",
        "README.md",
        "REFACTOR.md",
        "TASKS.md",
        "pyproject.toml",
        "setup.py",
        "plaivid",
        ".gitignore",
        ".gitattributes",
    }
)
MMD_KEYWORDS = (
    "flowchart",
    "graph ",
    "sequenceDiagram",
    "classDiagram",
    "stateDiagram",
    "erDiagram",
)
EVIDENCE_RE = re.compile(
    r"^(?P<path>[A-Za-z0-9_./ &-]+\.py)::"
    r"(?P<symbol>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)$"
)
LINK_RE = re.compile(r"\[[^\]\n]+\]\(([^)\n]+)\)")
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)


class Report:
    """Collect check results without writing anything."""

    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self.errors: list[str] = []
        self.checks: list[tuple[str, int]] = []
        self._errors_at_last_check = 0

    def fail(self, message: str) -> None:
        self.errors.append(message)

    def check(self, name: str, count: int) -> None:
        self.checks.append((name, count))
        new_errors = len(self.errors) - self._errors_at_last_check
        self._errors_at_last_check = len(self.errors)
        status = "OK  " if new_errors == 0 else "FAIL"
        print(f"{status} {name:<28} {count:>5} checked")

    def detail(self, message: str) -> None:
        if self.verbose:
            print(f"     {message}")


def doc_files() -> list[Path]:
    """Markdown files owned by this knowledge base (not third-party skills)."""
    files = sorted(BRAIN.rglob("*.md"))
    files.append(ROOT / "AGENTS.md")
    for name in SKILL_NAMES:
        files.append(SKILLS_DIR / name / "SKILL.md")
    return files


def strip_fences(text: str) -> str:
    """Blank out fenced blocks while preserving line numbering."""
    return FENCE_RE.sub(lambda match: "\n" * match.group(0).count("\n"), text)


def inline_tokens(text: str) -> list[tuple[int, str]]:
    """Return (line number, token) for inline code spans outside fenced blocks."""
    result: list[tuple[int, str]] = []
    cleaned = strip_fences(text)
    for number, line in enumerate(cleaned.splitlines(), start=1):
        # Inline spans never span lines; a line with an odd backtick count is ignored.
        if line.count("`") % 2:
            continue
        for token in INLINE_CODE_RE.findall(line):
            result.append((number, token.strip()))
    return result


def is_path_token(token: str) -> bool:
    if not token or any(char in token for char in ("*", "{", "}", "\n")):
        return False
    if "://" in token or token.startswith("#"):
        return False
    if " --" in token or token.startswith("-"):
        return False  # an inline shell command, not a path reference
    return token.startswith(PATH_ROOTS) or token in PATH_FILES


def relative(doc: Path) -> str:
    try:
        return str(doc.relative_to(ROOT))
    except ValueError:
        return str(doc)


def check_tree(report: Report) -> None:
    for item in REQUIRED_FILES:
        path = ROOT / item
        if not path.is_file():
            report.fail(f"[tree] missing required file: {item}")
        elif path.stat().st_size == 0:
            report.fail(f"[tree] empty required file: {item}")
    for path in sorted(BRAIN.rglob("*.md")):
        if path.stat().st_size == 0:
            report.fail(f"[tree] empty brain document: {relative(path)}")
    report.check("required tree", len(REQUIRED_FILES) + len(list(BRAIN.rglob("*.md"))))


def check_links(report: Report) -> None:
    total = 0
    for doc in doc_files():
        if not doc.exists():
            continue
        text = strip_fences(doc.read_text(encoding="utf-8"))
        for number, line in enumerate(text.splitlines(), start=1):
            for target in LINK_RE.findall(line):
                target = target.strip()
                if not target or target.startswith(("http://", "https://", "mailto:", "www.")):
                    continue
                total += 1
                path_part = target.split("#", 1)[0].split("?", 1)[0].strip()
                if not path_part:
                    continue  # anchor in the same document
                resolved = (doc.parent / path_part).resolve()
                if not resolved.exists():
                    report.fail(f"[links] {relative(doc)}:{number} unresolved link -> {target}")
                report.detail(f"link {relative(doc)}:{number} -> {path_part}")
    report.check("markdown links", total)


def check_paths(report: Report) -> None:
    total = 0
    seen: set[str] = set()
    for doc in doc_files():
        if not doc.exists():
            continue
        for number, token in inline_tokens(doc.read_text(encoding="utf-8")):
            candidate = token.split("::", 1)[0] if "::" in token else token
            if not is_path_token(candidate):
                continue
            total += 1
            seen.add(candidate)
            if not (ROOT / candidate).exists():
                report.fail(f"[paths] {relative(doc)}:{number} missing path -> {candidate}")
    report.check("referenced paths", total)
    report.check("unique paths", len(seen))


def module_symbols(path: Path) -> tuple[set[str], dict[str, set[str]]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    top: set[str] = set()
    members: dict[str, set[str]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            top.add(node.name)
            if isinstance(node, ast.ClassDef):
                names: set[str] = set()
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        names.add(child.name)
                    elif isinstance(child, ast.Assign):
                        for item in child.targets:
                            if isinstance(item, ast.Name):
                                names.add(item.id)
                    elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                        names.add(child.target.id)
                members[node.name] = names
        elif isinstance(node, ast.Assign):
            for item in node.targets:
                if isinstance(item, ast.Name):
                    top.add(item.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            top.add(node.target.id)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                top.add(alias.asname or alias.name)
    return top, members


def check_symbols(report: Report) -> None:
    total = 0
    cache: dict[Path, tuple[set[str], dict[str, set[str]]]] = {}
    for doc in doc_files():
        if not doc.exists():
            continue
        for number, token in inline_tokens(doc.read_text(encoding="utf-8")):
            match = EVIDENCE_RE.fullmatch(token)
            if match is None:
                continue
            total += 1
            path_text, symbol_text = match.group("path"), match.group("symbol")
            if not is_path_token(path_text):
                continue  # illustrative convention token, not a real evidence reference
            path = ROOT / path_text
            if not path.is_file():
                report.fail(f"[symbols] {relative(doc)}:{number} missing file {path_text}")
                continue
            if path not in cache:
                cache[path] = module_symbols(path)
            top, members = cache[path]
            parts = symbol_text.split(".")
            if parts[0] not in top:
                report.fail(
                    f"[symbols] {relative(doc)}:{number} missing symbol {path_text}::{symbol_text}"
                )
                continue
            current = members.get(parts[0], set())
            for part in parts[1:]:
                if part not in current:
                    report.fail(
                        f"[symbols] {relative(doc)}:{number} missing member "
                        f"{path_text}::{symbol_text}"
                    )
                    break
            report.detail(f"symbol {path_text}::{symbol_text}")
    report.check("evidence symbols", total)


def check_feature_map(report: Report) -> None:
    path = BRAIN / "codebase" / "FEATURE_TO_FILE_MAP.md"
    text = path.read_text(encoding="utf-8")
    blocks = re.split(r"(?=^### Feature: )", text, flags=re.MULTILINE)
    features = [block for block in blocks if block.startswith("### Feature: ")]
    for block in features:
        title = block.splitlines()[0].replace("### Feature: ", "")
        for field in FEATURE_FIELDS:
            if field not in block:
                report.fail(f"[features] '{title}' missing field {field}")
        refs = [token for _, token in inline_tokens(block)]
        paths = [
            token.split("::", 1)[0] for token in refs if is_path_token(token.split("::", 1)[0])
        ]
        for candidate in paths:
            if not (ROOT / candidate).exists():
                report.fail(f"[features] '{title}' references missing path {candidate}")
        if not any(item.startswith("plaivid_cli/") for item in paths):
            report.fail(f"[features] '{title}' has no implementation path")
        if not any(item.startswith("tests/") for item in paths):
            report.fail(f"[features] '{title}' has no test path")
    if len(features) < 10:
        report.fail(f"[features] only {len(features)} feature blocks documented")
    report.check("feature maps", len(features))


def check_entrypoints(report: Report) -> None:
    text = (BRAIN / "codebase" / "ENTRYPOINTS.md").read_text(encoding="utf-8")
    for token in ENTRYPOINT_TOKENS:
        if token not in text:
            report.fail(f"[entrypoints] ENTRYPOINTS.md is missing {token}")
    report.check("entry points", len(ENTRYPOINT_TOKENS))


def mermaid_ok(text: str, label: str, report: Report) -> None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or not lines[0].startswith(MMD_KEYWORDS):
        report.fail(f"[mermaid] {label} does not start with a diagram keyword")
        return
    body = "\n".join(lines)
    if not any(marker in body for marker in ("-->", "->>", "-.->", "---")):
        report.fail(f"[mermaid] {label} has no edges")
    openers = ("subgraph ", "alt ", "opt ", "loop ", "par ", "critical ", "rect ", "box ")
    opens = sum(1 for line in lines if line.startswith(openers))
    closes = sum(1 for line in lines if line == "end")
    if opens != closes:
        report.fail(f"[mermaid] {label} has {opens} subgraph / {closes} end")


def check_mermaid(report: Report) -> None:
    files = sorted((BRAIN / "diagrams").glob("*.mmd"))
    all_doc_text = "\n".join(
        path.read_text(encoding="utf-8") for path in doc_files() if path.exists()
    )
    for path in files:
        mermaid_ok(path.read_text(encoding="utf-8"), path.name, report)
        if f"diagrams/{path.name}" not in all_doc_text:
            report.fail(f"[mermaid] {path.name} is not referenced by any brain document")
    inline = 0
    for doc in doc_files():
        if not doc.exists():
            continue
        text = doc.read_text(encoding="utf-8")
        if text.count("```") % 2:
            report.fail(f"[mermaid] {relative(doc)} has unbalanced code fences")
        for block in re.findall(r"```mermaid\n(.*?)```", text, flags=re.DOTALL):
            inline += 1
            mermaid_ok(block, f"{relative(doc)} inline #{inline}", report)
    report.check("mermaid diagrams", len(files) + inline)


def check_skills(report: Report) -> None:
    for name in SKILL_NAMES:
        path = SKILLS_DIR / name / "SKILL.md"
        if not path.is_file():
            report.fail(f"[skills] missing {relative(path)}")
            continue
        text = path.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        if len(parts) < 3 or not parts[1].strip():
            report.fail(f"[skills] {name} has no YAML frontmatter")
            continue
        front = parts[1]
        field_name = re.search(r"^name:\s*(\S+)\s*$", front, flags=re.MULTILINE)
        description = re.search(r"^description:\s*(.+)$", front, flags=re.MULTILINE)
        if field_name is None or field_name.group(1) != name:
            report.fail(f"[skills] {name} frontmatter name mismatch")
        if description is None or not description.group(1).strip():
            report.fail(f"[skills] {name} frontmatter description missing")
        body = parts[2]
        for heading in SKILL_HEADINGS:
            if heading not in body:
                report.fail(f"[skills] {name} missing heading '{heading}'")
        if "docs/brain/" not in body:
            report.fail(f"[skills] {name} does not reference docs/brain/")
    report.check("skill definitions", len(SKILL_NAMES))


def check_agents(report: Report) -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    if "docs/brain/README.md" not in text:
        report.fail("[agents] AGENTS.md does not point to docs/brain/README.md")
    if "scripts/validate_brain.py" not in text:
        report.fail("[agents] AGENTS.md does not mention the audit script")
    for name in SKILL_NAMES:
        if name not in text:
            report.fail(f"[agents] AGENTS.md does not list skill {name}")
    steps = re.findall(r"^(\d+)\. ", text, flags=re.MULTILINE)
    if [int(item) for item in steps] != list(range(1, 12)):
        report.fail("[agents] AGENTS.md workflow is not the mandatory 11-step list")
    report.check("AGENTS.md", len(SKILL_NAMES) + 3)


def module_name(path: Path) -> str:
    """Dotted module name for a .py file (``__init__.py`` -> its package)."""
    parts = list(path.relative_to(ROOT).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def collect_edges() -> tuple[set[str], set[tuple[str, str]]]:
    """Deduplicated module-to-module import edges inside ``plaivid_cli/``.

    Counting rules (kept simple so the numbers can be reproduced):
      * every ``.py`` file under ``plaivid_cli/`` is a module, including legacy;
      * ``import x`` and ``from x import y`` count once per (source, target) pair;
      * ``from . import y`` resolves to the sibling module/package when it exists;
      * ``TYPE_CHECKING`` blocks count, so the charts type-only cycle is visible.
    """
    files = sorted(PKG.rglob("*.py"))
    names = {path: module_name(path) for path in files}
    known = set(names.values())
    edges: set[tuple[str, str]] = set()
    for path in files:
        source = names[path]
        package = ".".join(path.relative_to(ROOT).parent.parts)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            targets: list[str] = []
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    parts = package.split(".") if package else []
                    up = node.level - 1
                    base_parts = parts[: len(parts) - up] if up else parts
                    if node.module:
                        base_parts = base_parts + [node.module]
                    base = ".".join(base_parts)
                else:
                    base = node.module or ""
                for alias in node.names:
                    candidate = f"{base}.{alias.name}" if base else alias.name
                    targets.append(candidate if candidate in known else base)
            for target in targets:
                if target in known and target != source:
                    edges.add((source, target))
    return known, edges


def multi_node_sccs(modules: set[str], edges: set[tuple[str, str]]) -> list[list[str]]:
    """Tarjan strongly connected components of size > 1."""
    adjacency: dict[str, set[str]] = {module: set() for module in modules}
    for source, target in edges:
        adjacency[source].add(target)
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []
    counter = 0

    def visit(module: str) -> None:
        nonlocal counter
        index[module] = low[module] = counter
        counter += 1
        stack.append(module)
        on_stack.add(module)
        for neighbour in sorted(adjacency[module]):
            if neighbour not in index:
                visit(neighbour)
                low[module] = min(low[module], low[neighbour])
            elif neighbour in on_stack:
                low[module] = min(low[module], index[neighbour])
        if low[module] == index[module]:
            component: list[str] = []
            while True:
                item = stack.pop()
                on_stack.discard(item)
                component.append(item)
                if item == module:
                    break
            components.append(component)

    for module in sorted(modules):
        if module not in index:
            visit(module)
    return [sorted(component) for component in components if len(component) > 1]


def print_dependency_stats(modules: set[str], edges: set[tuple[str, str]]) -> None:
    """Print numbers used by DEPENDENCY_GRAPH.md so they can be refreshed."""
    active = {m for m in modules if not m.startswith("plaivid_cli.legacy")}
    active_edges = {(a, b) for a, b in edges if a in active}
    print("\nDependency statistics (deduplicated module-to-module edges)")
    print(
        f"  package modules      : {len(modules)} "
        f"({len(active)} active, {len(modules) - len(active)} legacy)"
    )
    print(f"  package edges        : {len(edges)} ({len(active_edges)} with an active source)")
    print(f"  active -> legacy     : {sum(1 for a, b in edges if a in active and b not in active)}")
    print(f"  legacy -> active     : {sum(1 for a, b in edges if a not in active and b in active)}")
    print(
        f"  legacy -> legacy     : "
        f"{sum(1 for a, b in edges if a not in active and b not in active)}"
    )
    sccs = multi_node_sccs(modules, edges)
    print(f"  multi-node SCCs      : {len(sccs)} {[' <-> '.join(c) for c in sccs]}")
    fan_in: dict[str, int] = {}
    fan_out: dict[str, int] = {}
    for source, target in active_edges:
        fan_out[source] = fan_out.get(source, 0) + 1
        fan_in[target] = fan_in.get(target, 0) + 1
    print("  top fan-in (active sources):")
    for module, count in sorted(fan_in.items(), key=lambda item: (-item[1], item[0]))[:8]:
        print(f"    {count:>3}  {module}")
    print("  top fan-out (active sources):")
    for module, count in sorted(fan_out.items(), key=lambda item: (-item[1], item[0]))[:8]:
        print(f"    {count:>3}  {module}")
    # (label, source prefix, target prefixes, excluded target prefix)
    layer_rules = (
        (
            "tui -> theme",
            "plaivid_cli.presentation.tui.",
            ("plaivid_cli.presentation.theme",),
            None,
        ),
        ("tui -> domain", "plaivid_cli.presentation.tui.", ("plaivid_cli.domain.",), None),
        (
            "overview_metrics -> models",
            "plaivid_cli.presentation.overview_metrics.",
            ("plaivid_cli.domain.models",),
            None,
        ),
        (
            "operations -> domain",
            "plaivid_cli.application.operations.",
            ("plaivid_cli.domain.",),
            None,
        ),
        (
            "pvm -> domain+infra",
            "plaivid_cli.infrastructure.pvm.",
            ("plaivid_cli.domain.", "plaivid_cli.infrastructure."),
            "plaivid_cli.infrastructure.pvm.",
        ),
        (
            "collection -> domain",
            "plaivid_cli.application.collection.",
            ("plaivid_cli.domain.",),
            None,
        ),
        (
            "cli -> app/domain/config",
            "plaivid_cli.presentation.cli.",
            ("plaivid_cli.application.", "plaivid_cli.domain.", "plaivid_cli.config"),
            None,
        ),
        (
            "bootstrap -> app/infra/cli/config",
            "plaivid_cli.bootstrap",
            (
                "plaivid_cli.application.",
                "plaivid_cli.infrastructure.",
                "plaivid_cli.presentation.cli.",
                "plaivid_cli.config",
            ),
            None,
        ),
    )
    print("  layer edge counts:")
    for label, source_prefix, targets, excluded in layer_rules:
        count = sum(
            1
            for a, b in active_edges
            if a.startswith(source_prefix)
            and any(b.startswith(target) for target in targets)
            and not (excluded and b.startswith(excluded))
        )
        print(f"    {count:>3}  {label}")
    print()


def check_legacy(report: Report, modules: set[str], edges: set[tuple[str, str]]) -> None:
    active = {m for m in modules if not m.startswith("plaivid_cli.legacy")}
    inbound = [f"{a} -> {b}" for a, b in edges if a in active and b not in active]
    if inbound:
        report.fail(f"[legacy] active modules import legacy: {inbound}")
    index = (BRAIN / "codebase" / "MODULE_INDEX.md").read_text(encoding="utf-8")
    if "**LEGACY**" not in index or "`plaivid_cli/legacy/`" not in index:
        report.fail("[legacy] MODULE_INDEX.md does not label the legacy tree")
    setup = (ROOT / "setup.py").read_text(encoding="utf-8")
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    if "plaivid_cli.legacy" not in setup:
        report.fail("[legacy] setup.py no longer excludes the legacy package")
    if "plaivid_cli.legacy*" not in project:
        report.fail("[legacy] pyproject.toml no longer excludes the legacy package")
    labelled = 0
    for doc in sorted(BRAIN.rglob("*.md")):
        for number, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            if "plaivid_cli/legacy/" in line:
                labelled += 1
                if "**CANONICAL**" in line:
                    report.fail(f"[legacy] {relative(doc)}:{number} labels a legacy path canonical")
    report.check("legacy labels", labelled)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    verbose = "--verbose" in args or "-v" in args
    print(f"Plaivid brain audit — {datetime.now(UTC).isoformat(timespec='seconds')}")
    print(f"Repository: {ROOT}\n")
    report = Report(verbose=verbose)
    modules, edges = collect_edges()
    check_tree(report)
    check_links(report)
    check_paths(report)
    check_symbols(report)
    check_feature_map(report)
    check_entrypoints(report)
    check_mermaid(report)
    check_skills(report)
    check_agents(report)
    check_legacy(report, modules, edges)
    if "--dependency-stats" in args:
        print_dependency_stats(modules, edges)
    print()
    if report.errors:
        print(f"FAILED — {len(report.errors)} issue(s):")
        for error in report.errors:
            print(f"  - {error}")
        return 1
    print("PASS — documentation tree, links, paths, symbols, features, entry points,")
    print("       diagrams, skills, AGENTS.md, and legacy labels are consistent.")
    print("This validator is read-only; no repository files were modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
