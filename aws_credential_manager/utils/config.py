"""Configuration management for AWS credential manager."""

import configparser
import os
from typing import Optional


# Default expiry thresholds (days)
DEFAULT_PASSWORD_MAX_AGE = 90
DEFAULT_ACCESS_KEY_MAX_AGE = 90

# Default vault name
DEFAULT_VAULT = "AWS"

# Password generation settings
DEFAULT_PASSWORD_LENGTH = 18


class ConfigManager:
    """Manages configuration for AWS credential manager."""

    def __init__(self, credentials_path: Optional[str] = None, vault_name: str = DEFAULT_VAULT):
        self.credentials_path = credentials_path or os.path.expanduser("~/.aws/credentials")
        self.vault_name = vault_name

    def get_aws_profiles(self) -> list[dict]:
        """Parse AWS credentials file and extract profile names."""
        if not os.path.exists(self.credentials_path):
            raise FileNotFoundError(f"AWS credentials file not found: {self.credentials_path}")

        config = configparser.ConfigParser()
        config.read(self.credentials_path)

        profiles = []
        for section in config.sections():
            if config.has_option(section, 'aws_access_key_id'):
                profiles.append({
                    'name': section,
                    'access_key_id': config.get(section, 'aws_access_key_id'),
                    'secret_access_key': config.get(section, 'aws_secret_access_key')
                })

        return profiles
