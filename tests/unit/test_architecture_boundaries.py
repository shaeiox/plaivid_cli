from __future__ import annotations

import ast
from pathlib import Path

PACKAGE = Path(__file__).parents[2] / "plaivid_cli"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def _forbidden(layer: str) -> set[str]:
    if layer == "domain":
        return {"plaivid_cli.application", "plaivid_cli.infrastructure", "plaivid_cli.tui", "plaivid_cli.cli", "plaivid_cli.bootstrap"}
    if layer == "application":
        return {"plaivid_cli.infrastructure", "plaivid_cli.tui", "plaivid_cli.cli", "plaivid_cli.bootstrap"}
    if layer == "infrastructure":
        return {"plaivid_cli.application", "plaivid_cli.tui", "plaivid_cli.cli", "plaivid_cli.bootstrap"}
    if layer in {"cli", "tui"}:
        return {"plaivid_cli.infrastructure", "plaivid_cli.bootstrap"}
    raise AssertionError(layer)


def test_domain_application_and_infrastructure_import_boundaries() -> None:
    layers = ("domain", "application", "infrastructure")
    violations = []
    for layer in layers:
        root = PACKAGE / layer
        for path in root.rglob("*.py"):
            for imported in _imports(path):
                if any(imported == prefix or imported.startswith(prefix + ".") for prefix in _forbidden(layer)):
                    violations.append(f"{path.relative_to(PACKAGE)} imports {imported}")
    assert violations == []


def test_presentations_do_not_import_infrastructure_or_bootstrap() -> None:
    violations = []
    for filename in ("cli.py", "tui.py"):
        for imported in _imports(PACKAGE / filename):
            if any(
                imported == prefix or imported.startswith(prefix + ".")
                for prefix in _forbidden(filename.removesuffix(".py"))
            ):
                violations.append(f"{filename} imports {imported}")
    assert violations == []
