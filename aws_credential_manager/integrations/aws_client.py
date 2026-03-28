"""AWS IAM CLI wrapper."""

import json
import subprocess


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
