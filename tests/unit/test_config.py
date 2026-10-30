from __future__ import annotations

import pytest

from plaivid_cli.config import ConfigurationError, Settings, load_settings


def test_settings_parse_trusted_argv_and_user_state_dir() -> None:
    settings = load_settings(
        {
            "PLAIVID_SBELL": "sudo sbell --safe-mode",
            "PLAIVID_RUNNING_VMS": "/usr/sbin/pvm-running-vms",
            "PLAIVID_STATE_DIR": "/tmp/plaivid-test",
            "PLAIVID_ALLOW_CREDENTIAL_ARGV": "1",
            "PLAIVID_CMD_TIMEOUT": "12",
        }
    )
    assert settings.sbell_argv == ("sudo", "sbell", "--safe-mode")
    assert settings.running_vms_argv == ("/usr/sbin/pvm-running-vms",)
    assert settings.allow_credential_argv is True
    assert settings.process_timeout == 12


def test_invalid_deadlines_and_empty_commands_are_rejected() -> None:
    with pytest.raises(ConfigurationError, match="TIMEOUT"):
        load_settings({"PLAIVID_CMD_TIMEOUT": "0"})
    with pytest.raises(ConfigurationError, match="PLAIVID_SBELL"):
        load_settings({"PLAIVID_SBELL": "  "})


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_non_finite_timeout_refresh_and_inventory_age_are_rejected(value: str) -> None:
    for name in ("PLAIVID_CMD_TIMEOUT", "PLAIVID_REFRESH"):
        with pytest.raises(ConfigurationError, match="finite positive"):
            load_settings({name: value})
    with pytest.raises(ConfigurationError, match="finite positive"):
        load_settings({"PLAIVID_MAX_INVENTORY_AGE_SECONDS": value})


def test_credentials_are_not_allowed_by_default_and_bulk_age_is_unset() -> None:
    settings: Settings = load_settings({})
    assert settings.allow_credential_argv is False
    assert settings.max_inventory_age_seconds is None
