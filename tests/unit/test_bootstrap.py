from __future__ import annotations

import json

import pytest

from plaivid_cli import bootstrap
from plaivid_cli.config import load_settings


def test_help_version_and_config_never_build_the_pvm_runtime(monkeypatch, capsys):
    def fail_if_composed(settings):
        raise AssertionError("configuration-only command constructed a PVM runtime")

    monkeypatch.setattr(bootstrap, "build_runtime", fail_if_composed)
    with pytest.raises(SystemExit) as help_exit:
        bootstrap.main(["--help"])
    assert help_exit.value.code == 0
    capsys.readouterr()

    with pytest.raises(SystemExit) as version_exit:
        bootstrap.main(["--version"])
    assert version_exit.value.code == 0
    assert "plaivid" in capsys.readouterr().out

    assert bootstrap.main(["config", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "validated"
    assert "credential_argv_acknowledged" in payload["data"]


def test_bootstrap_runtime_shutdown_closes_owned_collection_worker():
    runtime = bootstrap.build_runtime(load_settings({}))
    runtime.close()
    with pytest.raises(RuntimeError, match="closed"):
        runtime.collection.request_refresh("fake-token", sections=("inventory",))
