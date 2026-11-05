"""Build only the supported runtime; retired code remains checkout-only."""

from __future__ import annotations

from setuptools import find_packages, setup
from setuptools.command.build_py import build_py

LEGACY_PACKAGE = "plaivid_cli.legacy"
RUNTIME_PACKAGES = find_packages(
    include=["plaivid_cli*"],
    exclude=[f"{LEGACY_PACKAGE}*"],
)


class RuntimeBuildPy(build_py):
    """Exclude the retired implementation from distribution artifacts."""

    def find_package_modules(self, package: str, package_dir: str):
        if package == LEGACY_PACKAGE or package.startswith(f"{LEGACY_PACKAGE}."):
            return []
        return super().find_package_modules(package, package_dir)


if __name__ == "__main__":
    setup(
        packages=RUNTIME_PACKAGES,
        include_package_data=False,
        cmdclass={"build_py": RuntimeBuildPy},
    )
