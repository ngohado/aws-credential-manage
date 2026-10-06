"""Main orchestrator for AWS credential management."""

import json
import os
from datetime import datetime
from typing import cast

from ..integrations.aws_client import AWSClient
from ..integrations.bitwarden import BitwardenClient
from ..integrations.onepassword import OnePasswordClient
from ..integrations.vault_protocol import PasswordVault
from ..utils.config import (
    DEFAULT_ACCESS_KEY_MAX_AGE,
    DEFAULT_PASSWORD_MAX_AGE,
    DEFAULT_VAULT,
    DEFAULT_VAULT_TYPE,
    ConfigManager,
)
from .access_key_manager import AccessKeyManager
from .password_manager import PasswordManager


VAULT_CLIENTS: dict[str, type] = {
    "1password": OnePasswordClient,
    "bitwarden": BitwardenClient,
}


class CredentialManager:
    """Top-level orchestrator for all credential operations."""

    def __init__(self, credentials_path: str | None = None,
                 vault_name: str = DEFAULT_VAULT,
                 vault_type: str = DEFAULT_VAULT_TYPE):
        self.config = ConfigManager(credentials_path, vault_name)

        client_cls = VAULT_CLIENTS.get(vault_type)
        if client_cls is None:
            raise ValueError(
                f"Unknown vault type: {vault_type!r}. "
                f"Supported: {', '.join(sorted(VAULT_CLIENTS))}"
            )
        self.op: PasswordVault = cast(PasswordVault, client_cls(vault_name))
        self.aws = AWSClient()
        self.passwords = PasswordManager(self.aws, self.op, self.config)
        self.access_keys = AccessKeyManager(self.aws, self.op, self.config)

    def check_op_session(self) -> bool:
        """Check if 1Password CLI session is active."""
        return self.op.check_session()

    def list_profiles(self) -> None:
        """List all AWS profiles."""
        profiles = self.config.get_aws_profiles()
        print(f"Found {len(profiles)} AWS profiles:")
        for i, profile in enumerate(profiles, 1):
            profile_name = profile['name']
            print(f"{i:2d}. {profile_name}")
            print(f"     Access Key: {profile['access_key_id']}")
            print(f"     Vault Item: {profile_name}")
            print()

    def import_credentials(self, profile_name: str | None = None, dry_run: bool = False) -> bool:        
        """Import AWS access keys from credentials file to 1Password items."""
        profiles = self.config.get_aws_profiles()

        if profile_name:
            target_profiles = [p for p in profiles if p['name'] == profile_name]
            if not target_profiles:
                print(f"✗ Profile '{profile_name}' not found in AWS credentials")
                return False
        else:
            target_profiles = profiles

        if not target_profiles:
            print("✗ No profiles to import")
            return False

        print(f"Importing AWS credentials for {len(target_profiles)} profiles to vault...")        

        success_count = 0
        for profile in target_profiles:
            pname = profile['name']

            if dry_run:
                print(f"[DRY RUN] Would import credentials for '{pname}':")
                print(f"  Vault Item: {pname}")
                print(f"  AWS Access Key ID: {profile['access_key_id']}")
                print(f"  AWS Secret Key: {profile['secret_access_key'][:8]}...")
                print()
                success_count += 1
                continue

            try:
                item_title = self.passwords.get_item_title(pname)
                item_data = self.op.get_item(item_title)
                if not item_data:
                    print(f"✗ 1Password item not found: {item_title}")
                    continue

                has_access_key = (
                    self.op.get_field_value(item_data, 'aws_access_key_id') is not None
                )
                has_secret_key = (
                    self.op.get_field_value(item_data, 'aws_secret_access_key')
                    is not None
                )

                self.op.edit_item(item_title,
                                  **{
                                      'aws_access_key_id[text]':
                                          profile['access_key_id'],
                                      'aws_secret_access_key[password]':
                                          profile['secret_access_key'],
                                      'credential_import_date[text]':
                                          datetime.now().isoformat()
                                  })

                action = "Updated" if (has_access_key or has_secret_key) else "Added"
                print(f"✓ {action} AWS credentials in vault: {pname} - item title: {item_title}")
                success_count += 1

            except Exception as e:
                print(f"✗ Failed to import credentials for {pname} (item title: {item_title}): {e}")

        print(
            f"\n📊 Summary: {success_count}/{len(target_profiles)} profiles "
            "imported successfully"
        )
        return success_count == len(target_profiles)

    def quarterly_update(self, password_max_age: int | None = None,
                          access_key_max_age: int | None = None,
                          dry_run: bool = False) -> bool:
        """Update both passwords and access keys (quarterly maintenance)."""
        password_max_age = password_max_age or DEFAULT_PASSWORD_MAX_AGE
        access_key_max_age = access_key_max_age or DEFAULT_ACCESS_KEY_MAX_AGE

        if not self.check_op_session():
            return False

        print("🔄 Starting quarterly credential update (passwords + access keys)")
        print(f"Password policy: {password_max_age} days maximum age")
        print(f"Access key policy: {access_key_max_age} days maximum age")
        print("=" * 60)

        print("\n📍 Step 1: Updating expired passwords...")
        password_success = self.passwords.update_expired(password_max_age, dry_run)

        print("\n📍 Step 2: Updating outdated access keys...")
        access_key_success = self.access_keys.update_outdated(
            access_key_max_age, dry_run
        )

        print("\n" + "=" * 60)
        print("🎯 QUARTERLY CREDENTIAL UPDATE SUMMARY:")
        print(f"  Passwords: {'✅ Success' if password_success else '❌ Some failures'}")
        print(f"  Access Keys: {'✅ Success' if access_key_success else '❌ Some failures'}")

        overall_success = password_success and access_key_success
        overall_msg = (
            '✅ Complete success!' if overall_success else '⚠️ Check logs for issues'
        )
        print(f"  Overall: {overall_msg}")

        if not dry_run:
            self._log_quarterly_update({
                'timestamp': datetime.now().isoformat(),
                'type': 'quarterly_update',
                'password_max_age': password_max_age,
                'access_key_max_age': access_key_max_age,
                'password_success': password_success,
                'access_key_success': access_key_success,
                'overall_success': overall_success
            })

        return overall_success

    def _log_quarterly_update(self, log_entry: dict) -> None:
        """Log quarterly update results."""
        try:
            log_file = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "quarterly_updates.log"
            )
            with open(log_file, "a") as f:
                f.write(f"{json.dumps(log_entry)}\n")
            print(f"📝 Logged update to: {log_file}")
        except Exception as e:
            print(f"⚠️ Could not log quarterly update: {e}")
