from __future__ import annotations

import importlib.util
from pathlib import Path

from setuptools import Distribution, find_packages

ROOT = Path(__file__).parents[2]


def test_distribution_excludes_legacy_packages_and_entry_modules() -> None:
    packages = find_packages(
        where=str(ROOT),
        include=["plaivid_cli*"],
        exclude=["plaivid_cli.legacy*"],
    )
    assert "plaivid_cli" in packages
    assert "plaivid_cli.application" in packages
    assert "plaivid_cli.presentation" in packages
    assert "plaivid_cli.infrastructure.pvm" in packages
    assert not any(package == "plaivid_cli.legacy" or package.startswith("plaivid_cli.legacy.") for package in packages)

    spec = importlib.util.spec_from_file_location("plaivid_setup", ROOT / "setup.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.LEGACY_PACKAGE not in module.RUNTIME_PACKAGES
    assert "plaivid_cli.presentation" in module.RUNTIME_PACKAGES
    distribution = Distribution({"packages": module.RUNTIME_PACKAGES})
    distribution.script_name = str(ROOT / "setup.py")
    command = module.RuntimeBuildPy(distribution)
    command.initialize_options()
    root_modules = command.find_package_modules("plaivid_cli", str(ROOT / "plaivid_cli"))
    root_names = {name for _, name, _ in root_modules}
    assert "cli" not in root_names and "tui" not in root_names
    presentation_modules = command.find_package_modules(
        "plaivid_cli.presentation", str(ROOT / "plaivid_cli/presentation")
    )
    presentation_names = {name for _, name, _ in presentation_modules}
    assert {"cli", "tui"}.issubset(presentation_names)
    assert command.find_package_modules(
        "plaivid_cli.legacy", str(ROOT / "plaivid_cli/legacy")
    ) == []
    assert command.find_package_modules(
        "plaivid_cli.legacy.actions", str(ROOT / "plaivid_cli/legacy/actions")
    ) == []
