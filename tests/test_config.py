"""Tests for ConfigManager."""

from pathlib import Path

import pytest

from aws_credential_manager.utils.config import (
    DEFAULT_VAULT,
    ConfigManager,
)


class TestConfigManager:
    def test_defaults(self):
        cfg = ConfigManager()
        assert cfg.vault_name == DEFAULT_VAULT
        assert cfg.credentials_path.endswith("/.aws/credentials")

    def test_custom_vault(self):
        cfg = ConfigManager(vault_name="Other")
        assert cfg.vault_name == "Other"

    def test_get_aws_profiles_parses_valid_sections(self, aws_credentials_file: Path):
        cfg = ConfigManager(credentials_path=str(aws_credentials_file))
        profiles = cfg.get_aws_profiles()
        names = {p["name"] for p in profiles}
        assert names == {"profile-one", "profile-two"}

    def test_get_aws_profiles_skips_sections_without_key(
        self, aws_credentials_file: Path
    ):
        cfg = ConfigManager(credentials_path=str(aws_credentials_file))
        names = {p["name"] for p in cfg.get_aws_profiles()}
        assert "no-key-section" not in names

    def test_get_aws_profiles_returns_credentials(self, aws_credentials_file: Path):
        cfg = ConfigManager(credentials_path=str(aws_credentials_file))
        one = next(p for p in cfg.get_aws_profiles() if p["name"] == "profile-one")
        assert one["access_key_id"] == "AKIAONE"
        assert one["secret_access_key"] == "secretone"

    def test_missing_file_raises(self, tmp_path: Path):
        cfg = ConfigManager(credentials_path=str(tmp_path / "nope"))
        with pytest.raises(FileNotFoundError):
            cfg.get_aws_profiles()
