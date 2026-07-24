"""Configuration management for AWS credential manager."""

import configparser
import json
import os
from pathlib import Path

# Project root = repository root (two levels up from this file:
# aws_credential_manager/utils/config.py -> repo root).
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: str, environ: dict | None = None) -> None:
    """Load KEY=VALUE lines from a .env file into environ (default os.environ).

    Only sets a key when it is not already present, so real environment
    variables always take precedence. Best-effort: malformed lines and a
    missing file are ignored silently.
    """
    env = os.environ if environ is None else environ
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in env:
                env[key] = value


def _resolve_mapping_path(filename: str, project_root: Path) -> str:
    """Resolve a mapping filename: absolute as-is, relative under project_root."""
    p = Path(filename)
    if p.is_absolute():
        return str(p)
    return str(project_root / p)


# Load .env at import so env vars are available before constants resolve.
_load_dotenv(str(PROJECT_ROOT / ".env"))

# Default expiry thresholds (days)
DEFAULT_PASSWORD_MAX_AGE = 90
DEFAULT_ACCESS_KEY_MAX_AGE = 90

# Default vault name (env-overridable; built-in default matches docs).
DEFAULT_VAULT = os.environ.get("DEFAULT_VAULT", "AWS")

# Profile mapping filename (env-overridable).
PROFILE_MAPPING_FILE = os.environ.get("PROFILE_MAPPING_FILE", "profile_mapping.json")

# Password generation settings
DEFAULT_PASSWORD_LENGTH = 18


class ConfigManager:
    """Manages configuration for AWS credential manager."""

    def __init__(self, credentials_path: str | None = None, vault_name: str = DEFAULT_VAULT):
        self.credentials_path = credentials_path or os.path.expanduser("~/.aws/credentials")
        self.vault_name = vault_name
    
    def get_profile_mapping(self, profile_name: str) -> dict | None:
        # get from the file profile_mapping.json - this file is in the root folder of the project
        # it is here: /home/victor/code/github.com/nguyenquangkhai/aws-credential-manage/profile_mapping.json        
        mapping_file_path = '/home/victor/code/github.com/nguyenquangkhai/aws-credential-manage/profile_mapping.json'
        mapping_folder_path = os.path.dirname(mapping_file_path)
        # print(f"Debug - Looking for profile mapping in: {mapping_file_path} in folder: {mapping_folder_path}")
        if not os.path.exists(mapping_folder_path):
            print(f"⚠ Profile mapping file not found: {mapping_folder_path}")
            return None
        
        with open(mapping_file_path, 'r', encoding='utf-8') as f:
            try:
                mapping_data = json.load(f)                
                # print(f"Debug - Loaded profile mapping data: {mapping_data}")
                profile_mappings = mapping_data.get("profile_mappings", {})
                return profile_mappings.get(profile_name)
            except json.JSONDecodeError as e:
                print(f"⚠ Error parsing profile mapping file: {e}")
                return None
        
        profile_mappings = mapping_data.get("profile_mappings", {})
        return profile_mappings.get(profile_name)
        

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
