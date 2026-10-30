"""Build only the supported runtime; legacy modules remain checkout-only."""

from __future__ import annotations

from setuptools import find_packages, setup
from setuptools.command.build_py import build_py

LEGACY_ROOT_MODULES = frozenset(
    {"logs", "monitoring", "orchestrator", "render", "session", "theme", "transport", "vms"}
)
LEGACY_PACKAGES = frozenset({"plaivid_cli.actions", "plaivid_cli.commands"})
RUNTIME_PACKAGES = find_packages(
    include=["plaivid_cli*"],
    exclude=[
        "plaivid_cli.actions",
        "plaivid_cli.actions.*",
        "plaivid_cli.commands",
        "plaivid_cli.commands.*",
    ],
)


class RuntimeBuildPy(build_py):
    """Exclude retired, unsafe legacy modules from distribution artifacts."""

    def find_package_modules(self, package: str, package_dir: str):
        if package in LEGACY_PACKAGES or any(
            package.startswith(f"{legacy}.") for legacy in LEGACY_PACKAGES
        ):
            return []
        modules = super().find_package_modules(package, package_dir)
        if package != "plaivid_cli":
            return modules
        return [module for module in modules if module[1] not in LEGACY_ROOT_MODULES]


if __name__ == "__main__":
    setup(
        packages=RUNTIME_PACKAGES,
        include_package_data=False,
        cmdclass={"build_py": RuntimeBuildPy},
    )
