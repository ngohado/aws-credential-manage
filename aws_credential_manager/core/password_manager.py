"""Password management for AWS console passwords."""

from datetime import datetime

from ..integrations.aws_client import AWSClient
from ..integrations.onepassword import OnePasswordClient
from ..utils.config import DEFAULT_PASSWORD_MAX_AGE, ConfigManager


class PasswordManager:
    """Manages AWS console password rotation with 1Password sync."""

    def __init__(self, aws: AWSClient, op: OnePasswordClient, config: ConfigManager):
        self.aws = aws
        self.op = op
        self.config = config

    def get_password_age(self, profile_name: str) -> dict | None:
        """Get password age, preferring AWS IAM credential report over 1Password."""
        # --- Primary source: AWS IAM credential report ---
        try:
            aws_timestamp = self.aws.get_password_last_changed(profile_name)
            if aws_timestamp:
                last_date = datetime.fromisoformat(aws_timestamp.replace('Z', '+00:00'))
                age_days = (datetime.now(last_date.tzinfo) - last_date).days
                return {
                    'last_update': aws_timestamp,
                    'age_days': age_days,
                    'expired': age_days >= DEFAULT_PASSWORD_MAX_AGE,
                    'source': 'AWS IAM',
                }
        except Exception as e:
            print(f"⚠ Could not fetch AWS password age for {profile_name}: {e}")

        # --- Fallback: 1Password metadata ---
        item_data = self.op.get_item(profile_name)
        if not item_data:
            return None

        try:
            last_update = self.op.get_field_value(item_data, 'last_password_update')

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
                    'source': '1Password (fallback)',
                }
        except (ValueError, TypeError) as e:
            print(f"✗ Failed to get 1Password timestamp for {profile_name}: {e}")

        return None

    def update_profile(self, profile_name: str, dry_run: bool = False) -> bool:
        """Update AWS console password and store in 1Password."""
        if dry_run:
            print(f"[DRY RUN] Would update AWS console password for '{profile_name}':")
            print(f"  1Password Item: {profile_name}")
            print("  Actions:")
            print("    1. Generate secure password (18+ chars, meets AWS policy)")
            print("    2. Update AWS console password via IAM API")
            print("    3. Store new password in 1Password")
            return True

        # Check if AWS credentials are valid
        try:
            self.aws.get_user(profile_name)
        except Exception as e:
            print(f"⚠️ Skipping {profile_name}: Invalid AWS credentials")
            error_str = str(e)
            if "InvalidClientTokenId" in error_str:
                print("  Reason: AWS access keys are expired or invalid")
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
                              **{'last_password_update[text]': datetime.now().isoformat()})
            print(f"✓ Updated 1Password password for: {profile_name}")
        except Exception as e:
            print(f"✗ Failed to update 1Password for {profile_name}: {e}")
            return False

        print(f"✓ Successfully updated both AWS and 1Password for: {profile_name}")
        return True

    def list_expired(self, max_age_days: int | None = None) -> list[dict]:
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
                print("    Could not check password age")
                print()

        print(f"Summary: {len(expired_profiles)}/{len(profiles)} profiles have expired passwords")
        return expired_profiles

    def update_expired(self, max_age_days: int | None = None, dry_run: bool = False) -> bool:
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

        print(
            f"\n📊 Summary: {success_count}/{len(expired_profiles)} expired "
            "passwords updated successfully"
        )
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
