from __future__ import annotations

import importlib.util
from pathlib import Path

from setuptools import Distribution, find_packages

ROOT = Path(__file__).parents[2]


def test_distribution_excludes_legacy_packages_and_entry_modules() -> None:
    packages = find_packages(
        where=str(ROOT),
        include=["plaivid_cli*"],
        exclude=["plaivid_cli.actions*", "plaivid_cli.commands*"],
    )
    assert "plaivid_cli" in packages
    assert "plaivid_cli.application" in packages
    assert not any(
        package == "plaivid_cli.actions"
        or package.startswith("plaivid_cli.actions.")
        or package == "plaivid_cli.commands"
        or package.startswith("plaivid_cli.commands.")
        for package in packages
    )

    spec = importlib.util.spec_from_file_location("plaivid_setup", ROOT / "setup.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert "plaivid_cli.actions" not in module.RUNTIME_PACKAGES
    assert "plaivid_cli.commands" not in module.RUNTIME_PACKAGES
    distribution = Distribution({"packages": module.RUNTIME_PACKAGES})
    distribution.script_name = str(ROOT / "setup.py")
    command = module.RuntimeBuildPy(distribution)
    command.initialize_options()
    modules = command.find_package_modules("plaivid_cli", str(ROOT / "plaivid_cli"))
    names = {name for _, name, _ in modules}
    assert "cli" in names and "tui" in names
    assert not names.intersection(module.LEGACY_ROOT_MODULES)
    assert command.find_package_modules("plaivid_cli.actions", str(ROOT / "plaivid_cli/actions")) == []
    assert command.find_package_modules("plaivid_cli.commands", str(ROOT / "plaivid_cli/commands")) == []
