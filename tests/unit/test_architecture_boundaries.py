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
        return {
            "plaivid_cli.application",
            "plaivid_cli.infrastructure",
            "plaivid_cli.presentation",
            "plaivid_cli.bootstrap",
        }
    if layer == "application":
        return {
            "plaivid_cli.infrastructure",
            "plaivid_cli.presentation",
            "plaivid_cli.bootstrap",
        }
    if layer == "infrastructure":
        return {
            "plaivid_cli.application",
            "plaivid_cli.presentation",
            "plaivid_cli.bootstrap",
        }
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
                if any(
                    imported == prefix or imported.startswith(prefix + ".")
                    for prefix in _forbidden(layer)
                ):
                    violations.append(f"{path.relative_to(PACKAGE)} imports {imported}")
    assert violations == []


def test_presentations_do_not_import_infrastructure_or_bootstrap() -> None:
    violations = []
    for path in (PACKAGE / "presentation").rglob("*.py"):
        for imported in _imports(path):
            if any(
                imported == prefix or imported.startswith(prefix + ".")
                for prefix in _forbidden("cli")
            ):
                violations.append(f"{path.relative_to(PACKAGE)} imports {imported}")
    assert violations == []


def test_tui_pages_have_entry_points_and_page_scoped_components() -> None:
    tui = PACKAGE / "presentation" / "tui"
    expected = {
        "overview": "OverviewPage",
        "virtual_machines": "VirtualMachinePage",
        "virtual_desktops": "VirtualDesktopPage",
    }
    for page_name, entry_class in expected.items():
        page_dir = tui / "pages" / page_name
        page_source = page_dir / "page.py"
        components = page_dir / "components"
        assert page_source.is_file(), page_source
        assert components.is_dir() and list(components.glob("*.py")), components
        tree = ast.parse(page_source.read_text(encoding="utf-8"))
        assert any(
            isinstance(node, ast.ClassDef) and node.name == entry_class for node in tree.body
        ), f"{page_source} must define {entry_class}"

    cpu_component = tui / "pages" / "overview" / "components" / "cpu.py"
    cpu_tree = ast.parse(cpu_component.read_text(encoding="utf-8"))
    assert any(isinstance(node, ast.ClassDef) and node.name == "CPUCard" for node in cpu_tree.body)


def test_tui_components_are_presentation_only_and_shared_table_is_unique() -> None:
    tui = PACKAGE / "presentation" / "tui"
    component_dirs = [tui / "components"] + [
        path / "components" for path in (tui / "pages").iterdir() if path.is_dir()
    ]
    violations = []
    checkable_table_definitions = []
    forbidden_imports = _forbidden("tui") | {"plaivid_cli.application", "subprocess"}
    for component_dir in component_dirs:
        for path in component_dir.rglob("*.py"):
            for imported in _imports(path):
                if any(
                    imported == prefix or imported.startswith(prefix + ".")
                    for prefix in forbidden_imports
                ):
                    violations.append(f"{path.relative_to(PACKAGE)} imports {imported}")
            tree = ast.parse(path.read_text(encoding="utf-8"))
            checkable_table_definitions.extend(
                str(path.relative_to(PACKAGE))
                for node in ast.walk(tree)
                if isinstance(node, ast.ClassDef) and node.name == "CheckableTable"
            )
    assert violations == []
    assert checkable_table_definitions == ["presentation/tui/components/checkable_table.py"]


def test_tui_pages_do_not_import_sibling_page_implementations() -> None:
    pages_root = PACKAGE / "presentation" / "tui" / "pages"
    page_names = {path.name for path in pages_root.iterdir() if path.is_dir()}
    violations = []
    prefix = "plaivid_cli.presentation.tui.pages."
    for page_dir in pages_root.iterdir():
        if not page_dir.is_dir():
            continue
        for path in page_dir.rglob("*.py"):
            for imported in _imports(path):
                if not imported.startswith(prefix):
                    continue
                sibling = imported.removeprefix(prefix).split(".", 1)[0]
                if sibling in page_names and sibling != page_dir.name:
                    violations.append(f"{path.relative_to(PACKAGE)} imports sibling page {sibling}")
    assert violations == []
