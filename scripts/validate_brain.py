#!/usr/bin/env python3
"""Validate repository navigation and the two-project architecture without writes."""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "AGENTS.md", "README.md", "docs/brain/README.md",
    "docs/brain/codebase/REPOSITORY_MAP.md", "docs/brain/codebase/MODULE_INDEX.md",
    "docs/brain/codebase/ENTRYPOINTS.md", "docs/brain/codebase/FEATURE_TO_FILE_MAP.md",
    "docs/brain/contracts/API_CONTRACTS.md", "docs/brain/architecture/ENGINE_BOUNDARY.md",
    "docs/brain/workflows/BUILD.md", "docs/brain/workflows/DEVELOPMENT.md",
    "docs/brain/workflows/TESTING.md", "docs/brain/workflows/RELEASE.md",
    "UI/README.md", "UI/docs/IPC.md", "UI/docs/ENVIRONMENT.md", "UI/pyproject.toml",
    "pvm_control_engine/README.md", "pvm_control_engine/docs/ARCHITECTURE.md",
    "pvm_control_engine/docs/ENVIRONMENT.md",
    "pvm_control_engine/pyproject.toml", "scripts/validate_brain.py",
)
DOCS = (
    "README.md", "docs/brain/README.md", "docs/brain/codebase/REPOSITORY_MAP.md",
    "docs/brain/codebase/MODULE_INDEX.md", "docs/brain/codebase/ENTRYPOINTS.md",
    "docs/brain/codebase/FEATURE_TO_FILE_MAP.md", "docs/brain/contracts/API_CONTRACTS.md",
    "docs/brain/architecture/ENGINE_BOUNDARY.md", "docs/brain/workflows/BUILD.md",
    "docs/brain/workflows/DEVELOPMENT.md", "docs/brain/workflows/TESTING.md",
    "docs/brain/workflows/RELEASE.md", "UI/README.md", "UI/docs/IPC.md",
    "pvm_control_engine/README.md", "pvm_control_engine/docs/ARCHITECTURE.md",
)


def main() -> int:
    errors: list[str] = []
    for rel in REQUIRED:
        if not (ROOT / rel).is_file():
            errors.append(f"missing required project/navigation file: {rel}")

    # Check local Markdown links in the current navigation and product contract documents.
    links = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    checked_links = 0
    for rel in DOCS:
        path = ROOT / rel
        if not path.is_file():
            continue
        for target in links.findall(path.read_text(encoding="utf-8")):
            target = target.strip().split()[0].strip("<>") if target.strip() else ""
            if not target or target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target_path = target.split("#", 1)[0]
            if not target_path:
                continue
            checked_links += 1
            if not (path.parent / target_path).resolve().exists():
                errors.append(f"broken local link: {rel} -> {target_path}")

    # The release metadata and src layouts must define exactly two project identities.
    try:
        from_engine = (ROOT / "pvm_control_engine/pyproject.toml").read_text(encoding="utf-8")
        from_ui = (ROOT / "UI/pyproject.toml").read_text(encoding="utf-8")
        if 'name = "pvm-control-engine"' not in from_engine:
            errors.append("Engine distribution must be named pvm-control-engine")
        if 'name = "plaivid-ui"' not in from_ui:
            errors.append("UI distribution must be named plaivid-ui")
        if 'requires-python = ">=3.12"' not in from_engine or 'requires-python = ">=3.12"' not in from_ui:
            errors.append("both project distributions must retain the declared Python >=3.12 floor")
        if 'pvm-control-engine = "pvm_control_engine.bootstrap:main"' not in from_engine:
            errors.append("Engine console entry point is missing")
        if 'plaivid = "plaivid_ui.engine_client.cli:main"' not in from_ui:
            errors.append("UI console entry point is missing")
    except OSError as exc:
        errors.append(f"unable to read project metadata: {exc}")
    for rel in ("pvm_control_engine/src/pvm_control_engine/__init__.py", "UI/tui/src/plaivid_ui/__init__.py"):
        if not (ROOT / rel).is_file():
            errors.append(f"missing src-layout package root: {rel}")
    for forbidden in ("plaivid_cli", "setup.py"):
        if (ROOT / forbidden).exists():
            errors.append(f"obsolete third-product path still exists: {forbidden}")

    # Static dependency-direction guard: UI owns only the IPC client/DTO adaptation.
    ui_source = ROOT / "UI/tui/src/plaivid_ui"
    checked_modules = 0
    if ui_source.is_dir():
        for path in ui_source.rglob("*.py"):
            checked_modules += 1
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError as exc:
                errors.append(f"UI syntax error in {path.relative_to(ROOT)}: {exc}")
                continue
            for node in ast.walk(tree):
                module = node.module if isinstance(node, ast.ImportFrom) else None
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else []
                candidates = names + ([module] if module else [])
                for name in candidates:
                    if name and name.split(".", 1)[0] in {"plaivid_cli", "pvm_control_engine", "subprocess"}:
                        errors.append(f"forbidden UI import in {path.relative_to(ROOT)}: {name}")

    # Verify the explicit RPC registry is source-owned by the Engine and exists.
    registry = ROOT / "pvm_control_engine/src/pvm_control_engine/ipc/dispatcher.py"
    if not registry.is_file() or 'METHODS = {' not in registry.read_text(encoding="utf-8"):
        errors.append("Engine explicit RPC allowlist is missing")

    print("Plaivid two-project brain audit")
    print(f"  required files: {len(REQUIRED)}")
    print(f"  local documentation links: {checked_links}")
    print(f"  UI modules boundary-checked: {checked_modules}")
    if errors:
        print(f"FAIL — {len(errors)} issue(s):")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("PASS — project identities, entry points, IPC boundary, links and navigation are consistent.")
    print("Read-only; no repository files were modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
