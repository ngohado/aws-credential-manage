# Modular Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Split the monolithic `aws_credential_updater.py` into the existing `aws_credential_manager/` package structure with clear separation of concerns.

**Architecture:** Integration clients (`AWSClient`, `OnePasswordClient`) wrap all subprocess calls. Domain managers (`PasswordManager`, `AccessKeyManager`) contain business logic. `CredentialManager` orchestrates. CLI delegates to the orchestrator. Constants live in `utils/config.py`.

**Tech Stack:** Python 3.13, argparse, subprocess (AWS CLI + 1Password CLI)

---

### Task 1: Move constants to `utils/config.py`

**Files:**
- Modify: `aws_credential_manager/utils/config.py`

**Step 1: Update config.py with constants and credentials parsing**

```python
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
```

**Step 2: Update utils/__init__.py exports**

```python
"""Utility modules for configuration, logging, and validation."""

from .config import (
    ConfigManager,
    DEFAULT_PASSWORD_MAX_AGE,
    DEFAULT_ACCESS_KEY_MAX_AGE,
    DEFAULT_VAULT,
    DEFAULT_PASSWORD_LENGTH,
)
from .validators import validate_profile_name, validate_age_threshold

__all__ = [
    "ConfigManager",
    "DEFAULT_PASSWORD_MAX_AGE",
    "DEFAULT_ACCESS_KEY_MAX_AGE",
    "DEFAULT_VAULT",
    "DEFAULT_PASSWORD_LENGTH",
    "validate_profile_name",
    "validate_age_threshold",
]
```

**Step 3: Verify syntax**

Run: `python3 -c "from aws_credential_manager.utils.config import ConfigManager, DEFAULT_PASSWORD_MAX_AGE; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add aws_credential_manager/utils/config.py aws_credential_manager/utils/__init__.py
git commit -m "refactor: move constants and profile parsing to utils/config"
```

---

### Task 2: Create `integrations/aws_client.py`

**Files:**
- Create: `aws_credential_manager/integrations/aws_client.py`

**Step 1: Write the AWS client**

This wraps all `aws` CLI subprocess calls. Every method returns parsed data or raises on failure. No business logic here.

```python
"""AWS IAM CLI wrapper."""

import json
import subprocess
from datetime import datetime


class AWSClient:
    """Thin wrapper around AWS CLI IAM commands."""

    def get_user(self, profile_name: str) -> dict:
        """Get IAM user info for a profile."""
        result = subprocess.run([
            'aws', 'iam', 'get-user',
            '--profile', profile_name,
            '--output', 'json'
        ], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)['User']

    def update_login_profile(self, profile_name: str, username: str, password: str) -> None:
        """Update AWS console password."""
        subprocess.run([
            'aws', 'iam', 'update-login-profile',
            '--profile', profile_name,
            '--user-name', username,
            '--password', password,
            '--no-password-reset-required'
        ], check=True, capture_output=True)

    def list_access_keys(self, profile_name: str, username: str) -> list[dict]:
        """List access keys for a user."""
        result = subprocess.run([
            'aws', 'iam', 'list-access-keys',
            '--profile', profile_name,
            '--user-name', username,
            '--output', 'json'
        ], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)['AccessKeyMetadata']

    def create_access_key(self, profile_name: str, username: str) -> dict:
        """Create a new access key. Returns the AccessKey dict."""
        result = subprocess.run([
            'aws', 'iam', 'create-access-key',
            '--profile', profile_name,
            '--user-name', username,
            '--output', 'json'
        ], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)['AccessKey']

    def delete_access_key(self, profile_name: str, username: str, access_key_id: str) -> None:
        """Delete an access key."""
        subprocess.run([
            'aws', 'iam', 'delete-access-key',
            '--profile', profile_name,
            '--user-name', username,
            '--access-key-id', access_key_id
        ], capture_output=True, text=True, check=True)
```

**Step 2: Verify syntax**

Run: `python3 -c "from aws_credential_manager.integrations.aws_client import AWSClient; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add aws_credential_manager/integrations/aws_client.py
git commit -m "refactor: add AWSClient integration wrapper"
```

---

### Task 3: Create `integrations/onepassword.py`

**Files:**
- Create: `aws_credential_manager/integrations/onepassword.py`

**Step 1: Write the 1Password client**

Wraps all `op` CLI calls. Includes password generation (both 1P-based and fallback).

```python
"""1Password CLI wrapper."""

import json
import random
import string
import subprocess
from datetime import datetime
from typing import Optional

from ..utils.config import DEFAULT_PASSWORD_LENGTH


class OnePasswordClient:
    """Thin wrapper around 1Password CLI commands."""

    def __init__(self, vault_name: str = "AWS"):
        self.vault_name = vault_name

    def check_session(self) -> bool:
        """Check if 1Password CLI session is active."""
        try:
            subprocess.run(['op', 'account', 'list'],
                          capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError:
            print("Please sign in to 1Password CLI first:")
            print("Run: op signin")
            return False

    def get_item(self, title: str) -> Optional[dict]:
        """Get a 1Password item by title. Returns None if not found."""
        result = subprocess.run([
            'op', 'item', 'get', title,
            '--vault', self.vault_name,
            '--format', 'json'
        ], capture_output=True, text=True)

        if result.returncode != 0:
            return None
        return json.loads(result.stdout)

    def edit_item(self, title: str, **fields: str) -> None:
        """Update fields on a 1Password item.

        Usage: edit_item("my-item", password="secret", notes="hello")
        For typed fields use the 1Password notation in the key:
            edit_item("my-item", **{"field[text]": "value"})
        """
        cmd = ['op', 'item', 'edit', title, '--vault', self.vault_name]
        for key, value in fields.items():
            cmd.append(f'{key}={value}')
        subprocess.run(cmd, check=True, capture_output=True)

    def edit_item_generate_password(self, title: str, recipe: str = "letters,digits,symbols,18",
                                     **extra_fields: str) -> None:
        """Update a 1Password item with a generated password."""
        cmd = [
            'op', 'item', 'edit', title,
            '--vault', self.vault_name,
            f'--generate-password={recipe}',
        ]
        for key, value in extra_fields.items():
            cmd.append(f'{key}={value}')
        subprocess.run(cmd, check=True, capture_output=True)

    def get_field_value(self, item_data: dict, label: str) -> Optional[str]:
        """Extract a field value from 1Password item data by label."""
        for field in item_data.get('fields', []):
            if field.get('label') == label:
                return field.get('value')
        return None

    def generate_password(self, length: int = DEFAULT_PASSWORD_LENGTH) -> str:
        """Generate a secure password meeting AWS policy requirements."""
        uppercase = string.ascii_uppercase
        lowercase = string.ascii_lowercase
        digits = string.digits
        symbols = "!@#$%^&*()-_=+[]{}|;:,.<>?"

        password_chars = [
            random.choice(uppercase),
            random.choice(lowercase),
            random.choice(digits),
            random.choice(symbols),
        ]

        all_chars = uppercase + lowercase + digits + symbols
        for _ in range(length - 4):
            password_chars.append(random.choice(all_chars))

        random.shuffle(password_chars)
        return ''.join(password_chars)
```

**Step 2: Verify syntax**

Run: `python3 -c "from aws_credential_manager.integrations.onepassword import OnePasswordClient; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add aws_credential_manager/integrations/onepassword.py
git commit -m "refactor: add OnePasswordClient integration wrapper"
```

---

### Task 4: Create `core/password_manager.py`

**Files:**
- Create: `aws_credential_manager/core/password_manager.py`

**Step 1: Write the password manager**

Handles all password-related business logic. Uses `AWSClient` and `OnePasswordClient` via constructor injection.

```python
"""Password management for AWS console passwords."""

from datetime import datetime
from typing import Optional

from ..integrations.aws_client import AWSClient
from ..integrations.onepassword import OnePasswordClient
from ..utils.config import ConfigManager, DEFAULT_PASSWORD_MAX_AGE


class PasswordManager:
    """Manages AWS console password rotation with 1Password sync."""

    def __init__(self, aws: AWSClient, op: OnePasswordClient, config: ConfigManager):
        self.aws = aws
        self.op = op
        self.config = config

    def get_password_age(self, profile_name: str) -> Optional[dict]:
        """Get password age from 1Password last_password_update field."""
        item_data = self.op.get_item(profile_name)
        if not item_data:
            return None

        try:
            last_update = self.op.get_field_value(item_data, 'last_password_update')

            if not last_update:
                last_update = item_data.get('updated_at')

            if last_update:
                if 'T' in last_update:
                    last_date = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                else:
                    last_date = datetime.fromisoformat(last_update)

                age_days = (datetime.now(last_date.tzinfo) - last_date).days

                return {
                    'last_update': last_update,
                    'age_days': age_days,
                    'expired': age_days >= DEFAULT_PASSWORD_MAX_AGE,
                    'source': '1Password'
                }
        except (ValueError, TypeError) as e:
            print(f"✗ Failed to get 1Password timestamp for {profile_name}: {e}")

        return None

    def update_profile(self, profile_name: str, dry_run: bool = False) -> bool:
        """Update AWS console password and store in 1Password."""
        if dry_run:
            print(f"[DRY RUN] Would update AWS console password for '{profile_name}':")
            print(f"  1Password Item: {profile_name}")
            print(f"  Actions:")
            print(f"    1. Generate secure password (18+ chars, meets AWS policy)")
            print(f"    2. Update AWS console password via IAM API")
            print(f"    3. Store new password in 1Password")
            return True

        # Check if AWS credentials are valid
        try:
            self.aws.get_user(profile_name)
        except Exception as e:
            print(f"⚠️ Skipping {profile_name}: Invalid AWS credentials")
            error_str = str(e)
            if "InvalidClientTokenId" in error_str:
                print(f"  Reason: AWS access keys are expired or invalid")
            else:
                print(f"  Reason: {error_str}")
            print(f"  Note: Fix AWS credentials for {profile_name} to enable password updates")
            return False

        new_password = self.op.generate_password()

        # Update AWS console password
        try:
            user = self.aws.get_user(profile_name)
            self.aws.update_login_profile(profile_name, user['UserName'], new_password)
            print(f"✓ Updated AWS console password for user: {user['UserName']}")
        except Exception as e:
            print(f"✗ Failed to update AWS console password: {e}")
            return False

        # Update 1Password
        item_data = self.op.get_item(profile_name)
        if not item_data:
            print(f"✗ 1Password item not found: {profile_name}")
            return False

        try:
            self.op.edit_item(profile_name,
                              password=new_password,
                              **{f'last_password_update[text]': datetime.now().isoformat()})
            print(f"✓ Updated 1Password password for: {profile_name}")
        except Exception as e:
            print(f"✗ Failed to update 1Password for {profile_name}: {e}")
            return False

        print(f"✓ Successfully updated both AWS and 1Password for: {profile_name}")
        return True

    def list_expired(self, max_age_days: Optional[int] = None) -> list[dict]:
        """List all profiles with expired passwords."""
        max_age_days = max_age_days or DEFAULT_PASSWORD_MAX_AGE
        expired_profiles = []
        profiles = self.config.get_aws_profiles()

        print(f"Checking password age for {len(profiles)} profiles...")
        print(f"Password policy: {max_age_days} days maximum age\n")

        for profile in profiles:
            profile_name = profile['name']
            password_info = self.get_password_age(profile_name)

            if password_info:
                password_info['expired'] = password_info['age_days'] >= max_age_days
                status = "🔴 EXPIRED" if password_info['expired'] else "🟢 OK"
                print(f"{status} {profile_name}")
                print(f"    1Password: {profile_name}")

                if 'username' in password_info:
                    print(f"    User: {password_info['username']}")

                print(f"    Age: {password_info['age_days']} days")
                print(f"    Source: {password_info['source']}")

                if 'last_update' in password_info:
                    print(f"    Last Updated: {password_info['last_update']}")
                elif 'create_date' in password_info:
                    print(f"    Created: {password_info['create_date']}")

                print()

                if password_info['expired']:
                    expired_profiles.append({
                        'profile_name': profile_name,
                        'onepassword_title': profile_name,
                        **password_info
                    })
            else:
                print(f"⚠️  UNKNOWN {profile_name}")
                print(f"    1Password: {profile_name}")
                print(f"    Could not check password age")
                print()

        print(f"Summary: {len(expired_profiles)}/{len(profiles)} profiles have expired passwords")
        return expired_profiles

    def update_expired(self, max_age_days: Optional[int] = None, dry_run: bool = False) -> bool:
        """Update all profiles with expired passwords."""
        expired_profiles = self.list_expired(max_age_days)

        if not expired_profiles:
            print("✅ No expired passwords found!")
            return True

        print(f"\n🔄 Found {len(expired_profiles)} expired passwords")

        if dry_run:
            print("\n[DRY RUN] Would update the following expired passwords:")
            for profile in expired_profiles:
                print(f"  - {profile['profile_name']} (age: {profile['age_days']} days)")
            return True

        print("\nProceeding to update expired passwords...")

        success_count = 0
        for profile in expired_profiles:
            profile_name = profile['profile_name']
            print(f"\n🔄 Updating {profile_name} (age: {profile['age_days']} days)...")

            if self.update_profile(profile_name):
                success_count += 1
            else:
                print(f"❌ Failed to update {profile_name}")

        print(f"\n📊 Summary: {success_count}/{len(expired_profiles)} expired passwords updated successfully")
        return success_count == len(expired_profiles)

    def update_all(self, dry_run: bool = False) -> bool:
        """Update all profiles."""
        profiles = self.config.get_aws_profiles()
        profile_names = [p['name'] for p in profiles]

        print(f"Found {len(profile_names)} AWS profiles")

        success_count = 0
        for profile_name in profile_names:
            if self.update_profile(profile_name, dry_run):
                success_count += 1
            print()

        print(f"Summary: {success_count}/{len(profile_names)} profiles updated successfully")
        return success_count == len(profile_names)
```

**Step 2: Verify syntax**

Run: `python3 -c "from aws_credential_manager.core.password_manager import PasswordManager; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add aws_credential_manager/core/password_manager.py
git commit -m "refactor: add PasswordManager for password rotation logic"
```

---

### Task 5: Create `core/access_key_manager.py`

**Files:**
- Create: `aws_credential_manager/core/access_key_manager.py`

**Step 1: Write the access key manager**

Handles access key rotation, credentials file updates, rollback, and age tracking.

```python
"""Access key management for AWS IAM access keys."""

import configparser
import os
import subprocess
import time
from datetime import datetime
from typing import Optional

from ..integrations.aws_client import AWSClient
from ..integrations.onepassword import OnePasswordClient
from ..utils.config import ConfigManager, DEFAULT_ACCESS_KEY_MAX_AGE


class AccessKeyManager:
    """Manages AWS access key rotation with rollback support."""

    def __init__(self, aws: AWSClient, op: OnePasswordClient, config: ConfigManager):
        self.aws = aws
        self.op = op
        self.config = config

    def get_access_key_age(self, profile_name: str) -> Optional[dict]:
        """Get access key age from AWS API."""
        try:
            user = self.aws.get_user(profile_name)
            username = user['UserName']

            access_keys = self.aws.list_access_keys(profile_name, username)

            if not access_keys:
                print(f"✗ No access keys found for {profile_name}")
                return None

            # Get the current access key being used
            current_profiles = self.config.get_aws_profiles()
            current_access_key_id = None
            for profile in current_profiles:
                if profile['name'] == profile_name:
                    current_access_key_id = profile['access_key_id']
                    break

            current_key_info = None
            for key in access_keys:
                if key['AccessKeyId'] == current_access_key_id:
                    current_key_info = key
                    break

            if not current_key_info:
                print(f"⚠️ Current access key {current_access_key_id} not found in AWS (may be deleted)")
                return None

            create_date_str = current_key_info['CreateDate']
            if isinstance(create_date_str, str):
                create_date = datetime.fromisoformat(create_date_str.replace('Z', '+00:00'))
            else:
                create_date = create_date_str

            now = datetime.now(create_date.tzinfo) if create_date.tzinfo else datetime.now()
            age_days = (now - create_date).days

            return {
                'access_key_id': current_access_key_id,
                'username': username,
                'create_date': create_date_str,
                'age_days': age_days,
                'outdated': age_days >= DEFAULT_ACCESS_KEY_MAX_AGE,
                'status': current_key_info['Status'],
                'source': 'AWS API'
            }

        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to get access key info for {profile_name}: {e}")
            return None
        except Exception as e:
            print(f"✗ Error checking access key age for {profile_name}: {e}")
            return None

    def _update_credentials_file(self, profile_name: str, new_access_key_id: str,
                                  new_secret_key: str) -> bool:
        """Update the AWS credentials file with new access keys."""
        credentials_path = self.config.credentials_path
        try:
            backup_path = f"{credentials_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            subprocess.run(['cp', credentials_path, backup_path], check=True)
            print(f"✓ Created backup: {backup_path}")

            config = configparser.ConfigParser()
            config.read(credentials_path)

            if not config.has_section(profile_name):
                print(f"✗ Profile {profile_name} not found in credentials file")
                return False

            config.set(profile_name, 'aws_access_key_id', new_access_key_id)
            config.set(profile_name, 'aws_secret_access_key', new_secret_key)

            with open(credentials_path, 'w') as configfile:
                config.write(configfile)

            print(f"✓ Updated credentials file for profile: {profile_name}")
            return True

        except (subprocess.CalledProcessError, configparser.Error) as e:
            print(f"✗ Failed to update credentials file: {e}")
            return False

    def _restore_credentials_from_backup(self, profile_name: str) -> bool:
        """Restore credentials file from the most recent backup."""
        credentials_path = self.config.credentials_path
        try:
            backup_files = sorted([
                f for f in os.listdir(os.path.dirname(credentials_path))
                if f.startswith(f"{os.path.basename(credentials_path)}.backup.")
            ])

            if not backup_files:
                print(f"✗ No backup files found to restore from")
                return False

            latest_backup = os.path.join(os.path.dirname(credentials_path), backup_files[-1])
            subprocess.run(['cp', latest_backup, credentials_path], check=True)
            print(f"✓ Restored credentials from backup: {latest_backup}")
            return True

        except (subprocess.CalledProcessError, OSError) as e:
            print(f"✗ Failed to restore credentials from backup: {e}")
            print(f"  Please manually restore using: cp {credentials_path}.backup.* {credentials_path}")
            return False

    def _test_new_credentials(self, profile_name: str, max_retries: int = 5,
                               initial_delay: int = 2) -> bool:
        """Test new credentials with exponential backoff retry."""
        print(f"🔄 Testing new credentials for {profile_name}...")

        for attempt in range(max_retries):
            try:
                self.aws.get_user(profile_name)
                print(f"✓ New credentials for {profile_name} are working")
                return True
            except subprocess.CalledProcessError as e:
                if attempt < max_retries - 1:
                    if "InvalidClientTokenId" in str(e.stderr) or "The security token included in the request is invalid" in str(e.stderr):
                        delay = initial_delay * (2 ** attempt)
                        print(f"  Attempt {attempt + 1}/{max_retries}: Credentials still propagating, waiting {delay}s...")
                        time.sleep(delay)
                        continue
                    else:
                        print(f"✗ New credentials for {profile_name} failed with non-propagation error: {e}")
                        return False
                else:
                    print(f"✗ New credentials for {profile_name} failed after {max_retries} attempts: {e}")
                    print("  This may indicate an AWS service issue or the credentials are genuinely invalid")
                    return False

        return False

    def refresh_key(self, profile_name: str, dry_run: bool = False) -> bool:
        """Refresh (recreate) AWS access key for a profile with rollback support."""
        credentials_path = self.config.credentials_path

        if not os.path.exists(credentials_path):
            print(f"✗ AWS credentials file not found: {credentials_path}")
            return False

        config = configparser.ConfigParser()
        config.read(credentials_path)
        if not config.has_section(profile_name):
            print(f"✗ Profile '{profile_name}' not found in credentials file")
            return False

        if dry_run:
            print(f"[DRY RUN] Would refresh AWS access key for '{profile_name}':")
            print(f"  1Password Item: {profile_name}")
            print(f"  Actions:")
            print(f"    1. Get current user info and access keys")
            print(f"    2. Create new access key pair")
            print(f"    3. Update local credentials file (~/.aws/credentials)")
            print(f"    4. Wait for AWS credential propagation (3 seconds + retry logic)")
            print(f"    5. Test new credentials (up to 5 attempts with exponential backoff)")
            print(f"    6. Record access key refresh metadata in 1Password")
            print(f"    7. Delete old access key")
            print(f"  Note: Access keys will only be stored in ~/.aws/credentials (not in 1Password)")
            print(f"  Safety: Automatic rollback and cleanup if any step fails")
            return True

        print(f"🔄 Refreshing access key for: {profile_name}")

        # Step 1: Get user and check key count
        try:
            user = self.aws.get_user(profile_name)
            username = user['UserName']
            current_keys = self.aws.list_access_keys(profile_name, username)

            if len(current_keys) >= 2:
                print(f"✗ User {username} already has 2 access keys (AWS limit)")
                print("  Please delete an existing key before creating a new one")
                return False

            # Step 2: Create new access key
            new_key = self.aws.create_access_key(profile_name, username)
            print(f"✓ Created new access key for user: {username}")
            print(f"  New Access Key ID: {new_key['AccessKeyId']}")
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to create new access key for {profile_name}: {e}")
            return False

        old_access_key_id = current_keys[0]['AccessKeyId'] if current_keys else None

        # Step 3: Update local credentials file
        if not self._update_credentials_file(profile_name, new_key['AccessKeyId'], new_key['SecretAccessKey']):
            print(f"✗ Failed to update credentials file, cleaning up...")
            try:
                self.aws.delete_access_key(profile_name, username, new_key['AccessKeyId'])
            except Exception:
                pass
            return False

        # Step 4: Wait for propagation
        print(f"⏱️  Waiting for AWS credential propagation (3 seconds)...")
        time.sleep(3)

        # Step 5: Test new credentials
        if not self._test_new_credentials(profile_name):
            print(f"✗ New credentials failed testing, rolling back...")
            print(f"  Deleting newly created access key: {new_key['AccessKeyId']}")
            try:
                # Use default profile to clean up since the profile credentials may be broken
                subprocess.run([
                    'aws', 'iam', 'delete-access-key',
                    '--user-name', username,
                    '--access-key-id', new_key['AccessKeyId']
                ], capture_output=True, text=True, check=True)
                print(f"  ✓ Deleted failed access key: {new_key['AccessKeyId']}")
            except (subprocess.CalledProcessError, Exception) as e:
                print(f"  ⚠️ Could not delete failed access key {new_key['AccessKeyId']}: {e}")
                print(f"  Please manually delete it from the AWS console")

            print(f"  Attempting to restore credentials from backup...")
            if not self._restore_credentials_from_backup(profile_name):
                print(f"  Please manually restore credentials from backup file:")
                print(f"    cp {credentials_path}.backup.* {credentials_path}")

            return False

        # Step 6: Record metadata in 1Password
        try:
            self.op.edit_item(profile_name,
                              **{
                                  'last_access_key_refresh[text]': datetime.now().isoformat(),
                                  'current_access_key_id[text]': new_key['AccessKeyId']
                              })
            print(f"✓ Updated 1Password metadata for: {profile_name}")
        except subprocess.CalledProcessError:
            print(f"⚠️ Failed to update 1Password metadata, but access key refresh succeeded")

        # Step 7: Delete old access key
        if old_access_key_id:
            try:
                self.aws.delete_access_key(profile_name, username, old_access_key_id)
                print(f"✓ Deleted old access key: {old_access_key_id}")
            except Exception:
                print(f"⚠️ Failed to delete old access key: {old_access_key_id}")
                print(f"  New key is working, but please manually delete the old one")

        print(f"✓ Successfully refreshed access key for: {profile_name}")
        return True

    def refresh_all(self, dry_run: bool = False) -> bool:
        """Refresh access keys for all profiles."""
        profiles = self.config.get_aws_profiles()
        profile_names = [p['name'] for p in profiles]
        print(f"Refreshing access keys for {len(profile_names)} profiles...")

        success_count = 0
        for profile_name in profile_names:
            if self.refresh_key(profile_name, dry_run):
                success_count += 1
            print()

        print(f"Summary: {success_count}/{len(profile_names)} access keys refreshed successfully")
        return success_count == len(profile_names)

    def list_outdated(self, max_age_days: Optional[int] = None) -> list[dict]:
        """List all profiles with outdated access keys."""
        max_age_days = max_age_days or DEFAULT_ACCESS_KEY_MAX_AGE
        outdated_profiles = []
        profiles = self.config.get_aws_profiles()

        print(f"Checking access key age for {len(profiles)} profiles...")
        print(f"Access key policy: {max_age_days} days maximum age\n")

        for profile in profiles:
            profile_name = profile['name']
            access_key_info = self.get_access_key_age(profile_name)

            if access_key_info:
                access_key_info['outdated'] = access_key_info['age_days'] >= max_age_days

                status = "🔴 OUTDATED" if access_key_info['outdated'] else "🟢 OK"
                print(f"{status} {profile_name}")
                print(f"    1Password: {profile_name}")
                print(f"    User: {access_key_info['username']}")
                print(f"    Access Key: {access_key_info['access_key_id']}")
                print(f"    Age: {access_key_info['age_days']} days")
                print(f"    Status: {access_key_info['status']}")
                print(f"    Created: {access_key_info['create_date']}")
                print(f"    Source: {access_key_info['source']}")
                print()

                if access_key_info['outdated']:
                    outdated_profiles.append({
                        'profile_name': profile_name,
                        'onepassword_title': profile_name,
                        **access_key_info
                    })
            else:
                print(f"⚠️  UNKNOWN {profile_name}")
                print(f"    1Password: {profile_name}")
                print(f"    Could not check access key age")
                print()

        print(f"Summary: {len(outdated_profiles)}/{len(profiles)} profiles have outdated access keys")
        return outdated_profiles

    def update_outdated(self, max_age_days: Optional[int] = None, dry_run: bool = False) -> bool:
        """Update all profiles with outdated access keys."""
        outdated_profiles = self.list_outdated(max_age_days)

        if not outdated_profiles:
            print("✅ No outdated access keys found!")
            return True

        print(f"\n🔄 Found {len(outdated_profiles)} outdated access keys")

        if dry_run:
            print("\n[DRY RUN] Would refresh the following outdated access keys:")
            for profile in outdated_profiles:
                print(f"  - {profile['profile_name']} (age: {profile['age_days']} days)")
                print(f"    Access Key: {profile['access_key_id']}")
                print(f"    Created: {profile['create_date']}")
            return True

        print("\nProceeding to refresh outdated access keys...")

        success_count = 0
        for profile in outdated_profiles:
            profile_name = profile['profile_name']
            print(f"\n🔄 Refreshing {profile_name} (age: {profile['age_days']} days)...")
            print(f"  Current key: {profile['access_key_id']}")

            if self.refresh_key(profile_name):
                success_count += 1
            else:
                print(f"❌ Failed to refresh {profile_name}")

        print(f"\n📊 Summary: {success_count}/{len(outdated_profiles)} outdated access keys refreshed successfully")
        return success_count == len(outdated_profiles)
```

**Step 2: Verify syntax**

Run: `python3 -c "from aws_credential_manager.core.access_key_manager import AccessKeyManager; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add aws_credential_manager/core/access_key_manager.py
git commit -m "refactor: add AccessKeyManager for key rotation logic"
```

---

### Task 6: Create `core/credential_manager.py`

**Files:**
- Create: `aws_credential_manager/core/credential_manager.py`

**Step 1: Write the orchestrator**

Composes the managers and handles cross-cutting operations (quarterly update, import, list).

```python
"""Main orchestrator for AWS credential management."""

import json
import os
from datetime import datetime
from typing import Optional

from ..integrations.aws_client import AWSClient
from ..integrations.onepassword import OnePasswordClient
from ..utils.config import (
    ConfigManager,
    DEFAULT_PASSWORD_MAX_AGE,
    DEFAULT_ACCESS_KEY_MAX_AGE,
)
from .password_manager import PasswordManager
from .access_key_manager import AccessKeyManager


class CredentialManager:
    """Top-level orchestrator for all credential operations."""

    def __init__(self, credentials_path: Optional[str] = None, vault_name: str = "AWS"):
        self.config = ConfigManager(credentials_path, vault_name)
        self.aws = AWSClient()
        self.op = OnePasswordClient(vault_name)
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
            print(f"     1Password: {profile_name}")
            print()

    def import_credentials(self, profile_name: Optional[str] = None, dry_run: bool = False) -> bool:
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

        print(f"Importing AWS credentials for {len(target_profiles)} profiles to 1Password...")

        success_count = 0
        for profile in target_profiles:
            pname = profile['name']

            if dry_run:
                print(f"[DRY RUN] Would import credentials for '{pname}':")
                print(f"  1Password Item: {pname}")
                print(f"  AWS Access Key ID: {profile['access_key_id']}")
                print(f"  AWS Secret Key: {profile['secret_access_key'][:8]}...")
                print()
                success_count += 1
                continue

            try:
                item_data = self.op.get_item(pname)
                if not item_data:
                    print(f"✗ 1Password item not found: {pname}")
                    continue

                has_access_key = self.op.get_field_value(item_data, 'aws_access_key_id') is not None
                has_secret_key = self.op.get_field_value(item_data, 'aws_secret_access_key') is not None

                self.op.edit_item(pname,
                                  **{
                                      'aws_access_key_id[text]': profile['access_key_id'],
                                      'aws_secret_access_key[password]': profile['secret_access_key'],
                                      'credential_import_date[text]': datetime.now().isoformat()
                                  })

                action = "Updated" if (has_access_key or has_secret_key) else "Added"
                print(f"✓ {action} AWS credentials in 1Password: {pname}")
                success_count += 1

            except Exception as e:
                print(f"✗ Failed to import credentials for {pname}: {e}")

        print(f"\n📊 Summary: {success_count}/{len(target_profiles)} profiles imported successfully")
        return success_count == len(target_profiles)

    def quarterly_update(self, password_max_age: Optional[int] = None,
                          access_key_max_age: Optional[int] = None,
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
        access_key_success = self.access_keys.update_outdated(access_key_max_age, dry_run)

        print("\n" + "=" * 60)
        print("🎯 QUARTERLY CREDENTIAL UPDATE SUMMARY:")
        print(f"  Passwords: {'✅ Success' if password_success else '❌ Some failures'}")
        print(f"  Access Keys: {'✅ Success' if access_key_success else '❌ Some failures'}")

        overall_success = password_success and access_key_success
        print(f"  Overall: {'✅ Complete success!' if overall_success else '⚠️ Check logs for issues'}")

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
            log_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "quarterly_updates.log")
            with open(log_file, "a") as f:
                f.write(f"{json.dumps(log_entry)}\n")
            print(f"📝 Logged update to: {log_file}")
        except Exception as e:
            print(f"⚠️ Could not log quarterly update: {e}")
```

**Step 2: Verify syntax**

Run: `python3 -c "from aws_credential_manager.core.credential_manager import CredentialManager; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add aws_credential_manager/core/credential_manager.py
git commit -m "refactor: add CredentialManager orchestrator"
```

---

### Task 7: Create `cli/main.py`

**Files:**
- Create: `aws_credential_manager/cli/main.py`

**Step 1: Write the CLI module**

All argparse definitions and command dispatch. Delegates everything to `CredentialManager`.

```python
"""Command line interface for AWS credential manager."""

import argparse
import sys

from ..core.credential_manager import CredentialManager
from ..utils.config import DEFAULT_PASSWORD_MAX_AGE, DEFAULT_ACCESS_KEY_MAX_AGE


def main():
    parser = argparse.ArgumentParser(description='AWS Credential Password Updater with 1Password')
    parser.add_argument('--credentials-path', help='Path to AWS credentials file')
    parser.add_argument('--vault', default='AWS', help='1Password vault name (default: AWS)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be updated without making changes')

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # List command
    subparsers.add_parser('list', help='List all AWS profiles')

    # Update single profile
    update_parser = subparsers.add_parser('update', help='Update a specific profile')
    update_parser.add_argument('profile_name', help='Name of the profile to update')

    # Update all profiles
    subparsers.add_parser('update-all', help='Update all profiles')

    # List expired passwords
    expired_parser = subparsers.add_parser('list-expired', help='List profiles with expired passwords')
    expired_parser.add_argument('--max-age', type=int, default=DEFAULT_PASSWORD_MAX_AGE,
                               help=f'Maximum password age in days (default: {DEFAULT_PASSWORD_MAX_AGE})')

    # Update expired passwords
    update_expired_parser = subparsers.add_parser('update-expired', help='Update all expired passwords')
    update_expired_parser.add_argument('--max-age', type=int, default=DEFAULT_PASSWORD_MAX_AGE,
                                      help=f'Maximum password age in days (default: {DEFAULT_PASSWORD_MAX_AGE})')

    # Import credentials
    import_parser = subparsers.add_parser('import-credentials', help='Import AWS credentials to 1Password')
    import_parser.add_argument('profile_name', nargs='?', help='Profile name to import (optional, imports all if not specified)')

    # Import all credentials
    subparsers.add_parser('import-all-credentials', help='Import all AWS credentials to 1Password')

    # Refresh access key for single profile
    refresh_parser = subparsers.add_parser('refresh-access-key', help='Refresh (recreate) AWS access key for a specific profile')
    refresh_parser.add_argument('profile_name', help='Name of the profile to refresh access key for')

    # Refresh access keys for all profiles
    subparsers.add_parser('refresh-all-access-keys', help='Refresh access keys for all profiles')

    # List outdated access keys
    outdated_keys_parser = subparsers.add_parser('list-outdated-access-keys', help='List profiles with outdated access keys')
    outdated_keys_parser.add_argument('--max-age', type=int, default=DEFAULT_ACCESS_KEY_MAX_AGE,
                                     help=f'Maximum access key age in days (default: {DEFAULT_ACCESS_KEY_MAX_AGE})')

    # Update outdated access keys
    update_outdated_keys_parser = subparsers.add_parser('update-outdated-access-keys', help='Update all outdated access keys')
    update_outdated_keys_parser.add_argument('--max-age', type=int, default=DEFAULT_ACCESS_KEY_MAX_AGE,
                                             help=f'Maximum access key age in days (default: {DEFAULT_ACCESS_KEY_MAX_AGE})')

    # Quarterly update
    quarterly_parser = subparsers.add_parser('quarterly-update', help='Update both passwords and access keys (for scheduled maintenance)')
    quarterly_parser.add_argument('--password-max-age', type=int, default=DEFAULT_PASSWORD_MAX_AGE,
                                  help=f'Maximum password age in days (default: {DEFAULT_PASSWORD_MAX_AGE})')
    quarterly_parser.add_argument('--access-key-max-age', type=int, default=DEFAULT_ACCESS_KEY_MAX_AGE,
                                  help=f'Maximum access key age in days (default: {DEFAULT_ACCESS_KEY_MAX_AGE})')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    mgr = CredentialManager(args.credentials_path, args.vault)

    try:
        if args.command == 'list':
            mgr.list_profiles()
        elif args.command == 'update':
            if not mgr.check_op_session():
                return 1
            mgr.passwords.update_profile(args.profile_name, args.dry_run)
        elif args.command == 'update-all':
            if not mgr.check_op_session():
                return 1
            mgr.passwords.update_all(args.dry_run)
        elif args.command == 'list-expired':
            if not mgr.check_op_session():
                return 1
            mgr.passwords.list_expired(args.max_age)
        elif args.command == 'update-expired':
            if not mgr.check_op_session():
                return 1
            mgr.passwords.update_expired(args.max_age, args.dry_run)
        elif args.command == 'import-credentials':
            if not mgr.check_op_session():
                return 1
            profile_name = getattr(args, 'profile_name', None)
            mgr.import_credentials(profile_name, args.dry_run)
        elif args.command == 'import-all-credentials':
            if not mgr.check_op_session():
                return 1
            mgr.import_credentials(None, args.dry_run)
        elif args.command == 'refresh-access-key':
            if not mgr.check_op_session():
                return 1
            mgr.access_keys.refresh_key(args.profile_name, args.dry_run)
        elif args.command == 'refresh-all-access-keys':
            if not mgr.check_op_session():
                return 1
            mgr.access_keys.refresh_all(args.dry_run)
        elif args.command == 'list-outdated-access-keys':
            if not mgr.check_op_session():
                return 1
            mgr.access_keys.list_outdated(args.max_age)
        elif args.command == 'update-outdated-access-keys':
            if not mgr.check_op_session():
                return 1
            mgr.access_keys.update_outdated(args.max_age, args.dry_run)
        elif args.command == 'quarterly-update':
            if not mgr.check_op_session():
                return 1
            mgr.quarterly_update(args.password_max_age, args.access_key_max_age, args.dry_run)
    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
```

**Step 2: Verify syntax**

Run: `python3 -c "from aws_credential_manager.cli.main import main; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add aws_credential_manager/cli/main.py
git commit -m "refactor: add CLI module with argparse commands"
```

---

### Task 8: Update `aws_credential_updater.py` as thin entry point

**Files:**
- Modify: `aws_credential_updater.py`

**Step 1: Replace the monolith with a thin wrapper**

Keep the file as the entry point (for backward compatibility with existing scripts/automation) but delegate to the package.

```python
#!/usr/bin/env python3
"""AWS Credential Manager - Entry point.

This script delegates to the aws_credential_manager package.
For direct package usage: python -m aws_credential_manager
"""

__version__ = "1.0.0"

import sys
from aws_credential_manager.cli.main import main

if __name__ == '__main__':
    sys.exit(main())
```

**Step 2: Verify the CLI still works**

Run: `python3 aws_credential_updater.py --help`
Expected: Same help output as before with all subcommands listed.

**Step 3: Add `__main__.py` for package invocation**

Create `aws_credential_manager/__main__.py`:

```python
"""Allow running as: python -m aws_credential_manager"""

import sys
from .cli.main import main

sys.exit(main())
```

**Step 4: Verify package invocation**

Run: `python3 -m aws_credential_manager --help`
Expected: Same help output.

**Step 5: Commit**

```bash
git add aws_credential_updater.py aws_credential_manager/__main__.py
git commit -m "refactor: replace monolith with thin entry point delegating to package"
```

---

### Task 9: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Update architecture section**

Update the Core Architecture and Key Components sections to reflect the new package structure:

- Replace the single-file description with the package module layout
- Update the Key Components section to describe each module
- Keep all command examples unchanged (they still work the same way)
- Add note about `python -m aws_credential_manager` as an alternative entry point

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md to reflect modular package structure"
```
