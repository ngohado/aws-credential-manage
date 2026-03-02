#!/usr/bin/env python3

__version__ = "1.0.0"

import configparser
import subprocess
import os
import sys
import json
import secrets
import string
import time
from pathlib import Path
from datetime import datetime, timedelta

class AWSCredentialUpdater:
    def __init__(self, credentials_path=None, vault_name="AWS", mapping_file=None):
        self.credentials_path = credentials_path or os.path.expanduser("~/.aws/credentials")
        self.vault_name = vault_name
        self.op_session = None
        self.mapping_file = mapping_file or os.path.join(os.path.dirname(__file__), "profile_mapping.json")
        self.profile_mappings = self._load_mappings()
    
    def _load_mappings(self):
        """Load profile mappings from JSON file"""
        try:
            with open(self.mapping_file, 'r') as f:
                data = json.load(f)
                return data.get('profile_mappings', {})
        except FileNotFoundError:
            print(f"Warning: Mapping file not found: {self.mapping_file}")
            return {}
        except json.JSONDecodeError as e:
            print(f"Error parsing mapping file: {e}")
            return {}
        
    def generate_secure_password(self, length=18):
        """Generate a secure password using 1Password CLI matching AWS policy"""
        # AWS Policy: 18+ chars, uppercase, lowercase, numbers, symbols
        try:
            # Use 1Password's password generation with the required components
            password_recipe = f'letters,digits,symbols,{length}'
            
            # Create a temporary item just to generate the password
            temp_result = subprocess.run([
                'op', 'item', 'create',
                '--category', 'login',
                '--title', f'temp-pwd-{datetime.now().strftime("%Y%m%d_%H%M%S")}',
                '--vault', self.vault_name,
                f'--generate-password={password_recipe}',
                '--format', 'json'
            ], capture_output=True, text=True, check=True)
            
            temp_item = json.loads(temp_result.stdout)
            
            # Extract the generated password
            password = None
            for field in temp_item.get('fields', []):
                if field.get('purpose') == 'PASSWORD':
                    password = field.get('value')
                    break
            
            # Delete the temporary item
            subprocess.run([
                'op', 'item', 'delete', temp_item['id'],
                '--vault', self.vault_name
            ], capture_output=True)
            
            if password:
                return password
            else:
                raise ValueError("Could not extract password from generated item")
                
        except (subprocess.CalledProcessError, json.JSONDecodeError, ValueError) as e:
            print(f"✗ Failed to generate password with 1Password: {e}")
            # Fallback to manual generation that meets AWS policy
            return self._fallback_password_generation(length)
    
    def _fallback_password_generation(self, length=18):
        """Fallback password generation that meets AWS policy requirements"""
        import random
        
        # Ensure we meet AWS policy requirements
        uppercase = string.ascii_uppercase
        lowercase = string.ascii_lowercase  
        digits = string.digits
        symbols = "!@#$%^&*()-_=+[]{}|;:,.<>?"
        
        # Guarantee at least one of each required character type
        password_chars = [
            random.choice(uppercase),    # At least one uppercase
            random.choice(lowercase),    # At least one lowercase
            random.choice(digits),       # At least one digit
            random.choice(symbols),      # At least one symbol
        ]
        
        # Fill the rest with random characters from all categories
        all_chars = uppercase + lowercase + digits + symbols
        for _ in range(length - 4):
            password_chars.append(random.choice(all_chars))
        
        # Shuffle to avoid predictable pattern
        random.shuffle(password_chars)
        return ''.join(password_chars)
    
    def check_op_session(self):
        """Check if 1Password CLI session is active"""
        try:
            result = subprocess.run(['op', 'account', 'list'], 
                                  capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError:
            print("Please sign in to 1Password CLI first:")
            print("Run: op signin")
            return False
    
    def get_aws_profiles(self):
        """Parse AWS credentials file and extract profile names"""
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
    
    def get_1password_item_title(self, profile_name):
        """Get 1Password item title for AWS profile"""
        if profile_name in self.profile_mappings:
            return self.profile_mappings[profile_name]['onepassword_title']
        return None
    
    def add_aws_access_key_field(self, item_title, access_key_id, secret_key):
        """Add AWS access key fields to existing 1Password item"""
        try:
            # Add fields for AWS access keys
            subprocess.run([
                'op', 'item', 'edit', item_title,
                '--vault', self.vault_name,
                f'aws_access_key_id[text]={access_key_id}',
                f'aws_secret_access_key[password]={secret_key}',
                f'last_updated[text]={datetime.now().isoformat()}'
            ], check=True)
            print(f"✓ Added AWS access key fields to: {item_title}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to add AWS fields to {item_title}: {e}")
            return False
    
    def update_1password_item(self, profile_name, new_password=None):
        """Update existing 1Password item with new AWS console password"""
        item_title = self.get_1password_item_title(profile_name)
        
        if not item_title:
            print(f"✗ No 1Password mapping found for profile: {profile_name}")
            print(f"  Please add mapping in {self.mapping_file}")
            return False
        
        try:
            # Check if item exists
            result = subprocess.run([
                'op', 'item', 'get', item_title, '--vault', self.vault_name, '--format', 'json'
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"✗ 1Password item not found: {item_title}")
                return False
            
            # Update the password field directly using 1Password's generator
            subprocess.run([
                'op', 'item', 'edit', item_title,
                '--vault', self.vault_name,
                '--generate-password=letters,digits,symbols,18',
                f'last_password_update[text]={datetime.now().isoformat()}'
            ], check=True)
            print(f"✓ Updated 1Password password for: {item_title}")
                
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to update 1Password for {profile_name}: {e}")
            return False
        except json.JSONDecodeError as e:
            print(f"✗ Failed to parse 1Password item data: {e}")
            return False
        
        return True
    
    def update_1password_item_with_password(self, profile_name, password):
        """Update existing 1Password item with specific password"""
        item_title = self.get_1password_item_title(profile_name)
        
        if not item_title:
            print(f"✗ No 1Password mapping found for profile: {profile_name}")
            return False
        
        try:
            # Check if item exists
            result = subprocess.run([
                'op', 'item', 'get', item_title, '--vault', self.vault_name, '--format', 'json'
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"✗ 1Password item not found: {item_title}")
                return False
            
            # Update the password field with the specific password
            subprocess.run([
                'op', 'item', 'edit', item_title,
                '--vault', self.vault_name,
                f'password={password}',
                f'last_password_update[text]={datetime.now().isoformat()}'
            ], check=True)
            print(f"✓ Updated 1Password password for: {item_title}")
                
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to update 1Password for {profile_name}: {e}")
            return False
        except json.JSONDecodeError as e:
            print(f"✗ Failed to parse 1Password item data: {e}")
            return False
        
        return True
    
    def update_aws_console_password(self, profile_name, new_password):
        """Update AWS console password using AWS CLI"""
        try:
            # First get the current user name
            get_user_result = subprocess.run([
                'aws', 'iam', 'get-user',
                '--profile', profile_name,
                '--output', 'json'
            ], capture_output=True, text=True, check=True)
            
            user_info = json.loads(get_user_result.stdout)
            username = user_info['User']['UserName']
            
            # Update the login profile password
            subprocess.run([
                'aws', 'iam', 'update-login-profile',
                '--profile', profile_name,
                '--user-name', username,
                '--password', new_password,
                '--no-password-reset-required'
            ], check=True, capture_output=True)
            
            print(f"✓ Updated AWS console password for user: {username}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to update AWS console password: {e}")
            if e.stderr:
                error_msg = e.stderr.decode().strip() if isinstance(e.stderr, bytes) else str(e.stderr).strip()
                print(f"  Error details: {error_msg}")
            return False
        except json.JSONDecodeError as e:
            print(f"✗ Failed to parse AWS response: {e}")
            return False
    
    def get_password_age_from_1password(self, profile_name):
        """Get password age from 1Password last_password_update field"""
        item_title = self.get_1password_item_title(profile_name)
        if not item_title:
            return None
            
        try:
            result = subprocess.run([
                'op', 'item', 'get', item_title, '--vault', self.vault_name, '--format', 'json'
            ], capture_output=True, text=True, check=True)
            
            item_data = json.loads(result.stdout)
            
            # Look for last_password_update field
            last_update = None
            for field in item_data.get('fields', []):
                if field.get('label') == 'last_password_update':
                    last_update = field.get('value')
                    break
            
            # If no last update found, use item's updated_at
            if not last_update:
                last_update = item_data.get('updated_at')
            
            if last_update:
                # Parse ISO timestamp
                if 'T' in last_update:
                    last_date = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                else:
                    last_date = datetime.fromisoformat(last_update)
                
                age_days = (datetime.now(last_date.tzinfo) - last_date).days
                
                return {
                    'last_update': last_update,
                    'age_days': age_days,
                    'expired': age_days >= 90,
                    'source': '1Password'
                }
        
        except (subprocess.CalledProcessError, json.JSONDecodeError, ValueError) as e:
            print(f"✗ Failed to get 1Password timestamp for {profile_name}: {e}")
        
        return None

    def create_new_access_key(self, profile_name):
        """Create a new AWS access key for the user"""
        try:
            # First get the current user name
            get_user_result = subprocess.run([
                'aws', 'iam', 'get-user',
                '--profile', profile_name,
                '--output', 'json'
            ], capture_output=True, text=True, check=True)
            
            user_info = json.loads(get_user_result.stdout)
            username = user_info['User']['UserName']
            
            # Check how many access keys the user currently has
            list_keys_result = subprocess.run([
                'aws', 'iam', 'list-access-keys',
                '--profile', profile_name,
                '--user-name', username,
                '--output', 'json'
            ], capture_output=True, text=True, check=True)
            
            keys_info = json.loads(list_keys_result.stdout)
            current_keys = keys_info['AccessKeyMetadata']
            
            if len(current_keys) >= 2:
                print(f"✗ User {username} already has 2 access keys (AWS limit)")
                print("  Please delete an existing key before creating a new one")
                return None
            
            # Create new access key
            create_key_result = subprocess.run([
                'aws', 'iam', 'create-access-key',
                '--profile', profile_name,
                '--user-name', username,
                '--output', 'json'
            ], capture_output=True, text=True, check=True)
            
            new_key_info = json.loads(create_key_result.stdout)
            access_key = new_key_info['AccessKey']
            
            print(f"✓ Created new access key for user: {username}")
            print(f"  New Access Key ID: {access_key['AccessKeyId']}")
            
            return {
                'username': username,
                'access_key_id': access_key['AccessKeyId'],
                'secret_access_key': access_key['SecretAccessKey'],
                'old_keys': current_keys
            }
            
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to create new access key for {profile_name}: {e}")
            if e.stderr:
                error_msg = e.stderr.decode().strip() if isinstance(e.stderr, bytes) else str(e.stderr).strip()
                print(f"  Error details: {error_msg}")
            return None
        except json.JSONDecodeError as e:
            print(f"✗ Failed to parse AWS response: {e}")
            return None

    def update_credentials_file(self, profile_name, new_access_key_id, new_secret_key):
        """Update the AWS credentials file with new access keys"""
        try:
            # Create backup first
            backup_path = f"{self.credentials_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            subprocess.run(['cp', self.credentials_path, backup_path], check=True)
            print(f"✓ Created backup: {backup_path}")
            
            # Read and update credentials file
            config = configparser.ConfigParser()
            config.read(self.credentials_path)
            
            if not config.has_section(profile_name):
                print(f"✗ Profile {profile_name} not found in credentials file")
                return False
            
            # Update the access key and secret
            config.set(profile_name, 'aws_access_key_id', new_access_key_id)
            config.set(profile_name, 'aws_secret_access_key', new_secret_key)
            
            # Write updated file
            with open(self.credentials_path, 'w') as configfile:
                config.write(configfile)
            
            print(f"✓ Updated credentials file for profile: {profile_name}")
            return True
            
        except (subprocess.CalledProcessError, configparser.Error) as e:
            print(f"✗ Failed to update credentials file: {e}")
            return False

    def restore_credentials_from_backup(self, profile_name, old_access_key_id, old_secret_key):
        """Restore credentials file from backup when rollback is needed"""
        try:
            # Find the most recent backup file
            backup_files = sorted([f for f in os.listdir(os.path.dirname(self.credentials_path)) 
                                  if f.startswith(f"{os.path.basename(self.credentials_path)}.backup.")])
            
            if not backup_files:
                print(f"✗ No backup files found to restore from")
                return False
            
            latest_backup = os.path.join(os.path.dirname(self.credentials_path), backup_files[-1])
            subprocess.run(['cp', latest_backup, self.credentials_path], check=True)
            print(f"✓ Restored credentials from backup: {latest_backup}")
            return True
            
        except (subprocess.CalledProcessError, OSError) as e:
            print(f"✗ Failed to restore credentials from backup: {e}")
            print(f"  Please manually restore using: cp {self.credentials_path}.backup.* {self.credentials_path}")
            return False

    def delete_old_access_key(self, profile_name, old_access_key_id):
        """Delete the old AWS access key"""
        try:
            # Get username first
            get_user_result = subprocess.run([
                'aws', 'iam', 'get-user',
                '--profile', profile_name,
                '--output', 'json'
            ], capture_output=True, text=True, check=True)
            
            user_info = json.loads(get_user_result.stdout)
            username = user_info['User']['UserName']
            
            # Delete the old access key
            subprocess.run([
                'aws', 'iam', 'delete-access-key',
                '--profile', profile_name,
                '--user-name', username,
                '--access-key-id', old_access_key_id
            ], capture_output=True, text=True, check=True)
            
            print(f"✓ Deleted old access key: {old_access_key_id}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to delete old access key {old_access_key_id}: {e}")
            if e.stderr:
                error_msg = e.stderr.decode().strip() if isinstance(e.stderr, bytes) else str(e.stderr).strip()
                print(f"  Error details: {error_msg}")
            return False
        except json.JSONDecodeError as e:
            print(f"✗ Failed to parse AWS response: {e}")
            return False

    def test_new_credentials(self, profile_name, max_retries=5, initial_delay=2):
        """Test if the new credentials work by making a simple AWS API call with retry logic"""
        print(f"🔄 Testing new credentials for {profile_name}...")
        
        for attempt in range(max_retries):
            try:
                subprocess.run([
                    'aws', 'iam', 'get-user',
                    '--profile', profile_name,
                    '--output', 'json'
                ], capture_output=True, text=True, check=True)
                
                print(f"✓ New credentials for {profile_name} are working")
                return True
                
            except subprocess.CalledProcessError as e:
                if attempt < max_retries - 1:
                    # Check if it's a credential propagation issue
                    if "InvalidClientTokenId" in str(e.stderr) or "The security token included in the request is invalid" in str(e.stderr):
                        delay = initial_delay * (2 ** attempt)  # Exponential backoff
                        print(f"  Attempt {attempt + 1}/{max_retries}: Credentials still propagating, waiting {delay}s...")
                        time.sleep(delay)
                        continue
                    else:
                        # Different error, don't retry
                        print(f"✗ New credentials for {profile_name} failed with non-propagation error: {e}")
                        return False
                else:
                    # Final attempt failed
                    print(f"✗ New credentials for {profile_name} failed after {max_retries} attempts: {e}")
                    print("  This may indicate an AWS service issue or the credentials are genuinely invalid")
                    return False
        
        return False

    def refresh_access_key(self, profile_name, dry_run=False):
        """Refresh (recreate) AWS access key for a profile"""
        # Check if profile mapping exists
        onepassword_title = self.get_1password_item_title(profile_name)
        if not onepassword_title:
            print(f"✗ No 1Password mapping found for profile: {profile_name}")
            return False
        
        # Check if credentials file exists
        if not os.path.exists(self.credentials_path):
            print(f"✗ AWS credentials file not found: {self.credentials_path}")
            return False
        
        # Check if profile exists in credentials file
        config = configparser.ConfigParser()
        config.read(self.credentials_path)
        if not config.has_section(profile_name):
            print(f"✗ Profile '{profile_name}' not found in credentials file")
            return False
        
        if dry_run:
            print(f"[DRY RUN] Would refresh AWS access key for '{profile_name}':")
            print(f"  1Password Item: {onepassword_title}")
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
        
        # Step 1: Create new access key
        key_info = self.create_new_access_key(profile_name)
        if not key_info:
            return False
        
        old_access_key_id = None
        if key_info['old_keys']:
            old_access_key_id = key_info['old_keys'][0]['AccessKeyId']
        
        # Step 2: Update local credentials file
        if not self.update_credentials_file(profile_name, key_info['access_key_id'], key_info['secret_access_key']):
            print(f"✗ Failed to update credentials file, cleaning up...")
            # Cleanup: delete the new key we just created
            self.delete_old_access_key(profile_name, key_info['access_key_id'])
            return False
        
        # Step 3: Wait a moment for AWS credential propagation
        print(f"⏱️  Waiting for AWS credential propagation (3 seconds)...")
        time.sleep(3)
        
        # Step 4: Test new credentials
        if not self.test_new_credentials(profile_name):
            print(f"✗ New credentials failed testing, rolling back...")
            # Try to delete the new key we just created
            print(f"  Deleting newly created access key: {key_info['access_key_id']}")
            try:
                # Use a different profile or get username directly to delete the failed key
                get_user_result = subprocess.run([
                    'aws', 'iam', 'get-user',
                    '--output', 'json'
                ], capture_output=True, text=True, check=True)
                
                user_info = json.loads(get_user_result.stdout)
                username = user_info['User']['UserName']
                
                subprocess.run([
                    'aws', 'iam', 'delete-access-key',
                    '--user-name', username,
                    '--access-key-id', key_info['access_key_id']
                ], capture_output=True, text=True, check=True)
                
                print(f"  ✓ Deleted failed access key: {key_info['access_key_id']}")
                
            except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
                print(f"  ⚠️ Could not delete failed access key {key_info['access_key_id']}: {e}")
                print(f"  Please manually delete it from the AWS console")
            
            # Try to restore from backup
            print(f"  Attempting to restore credentials from backup...")
            if not self.restore_credentials_from_backup(profile_name, old_access_key_id, None):
                print(f"  Please manually restore credentials from backup file:")
                print(f"    cp {self.credentials_path}.backup.* {self.credentials_path}")
            
            return False
        
        # Step 5: Record access key refresh in 1Password (metadata only, not the actual keys)
        try:
            subprocess.run([
                'op', 'item', 'edit', onepassword_title,
                '--vault', self.vault_name,
                f'last_access_key_refresh[text]={datetime.now().isoformat()}',
                f'current_access_key_id[text]={key_info["access_key_id"]}'
            ], check=True, capture_output=True)
            print(f"✓ Updated 1Password metadata for: {onepassword_title}")
        except subprocess.CalledProcessError:
            print(f"⚠️ Failed to update 1Password metadata, but access key refresh succeeded")
        
        # Step 6: Delete old access key
        if old_access_key_id:
            if not self.delete_old_access_key(profile_name, old_access_key_id):
                print(f"⚠️ Failed to delete old access key: {old_access_key_id}")
                print(f"  New key is working, but please manually delete the old one")
        
        print(f"✓ Successfully refreshed access key for: {profile_name}")
        return True

    def refresh_all_access_keys(self, dry_run=False):
        """Refresh access keys for all mapped profiles"""
        if not self.check_op_session():
            return False
        
        mapped_profiles = list(self.profile_mappings.keys())
        print(f"Refreshing access keys for {len(mapped_profiles)} mapped profiles...")
        
        success_count = 0
        for profile_name in mapped_profiles:
            if self.refresh_access_key(profile_name, dry_run):
                success_count += 1
            print()  # Empty line for readability
        
        print(f"Summary: {success_count}/{len(mapped_profiles)} access keys refreshed successfully")
        return success_count == len(mapped_profiles)

    def get_access_key_age(self, profile_name):
        """Get access key age from AWS API"""
        try:
            # Get current user name
            get_user_result = subprocess.run([
                'aws', 'iam', 'get-user',
                '--profile', profile_name,
                '--output', 'json'
            ], capture_output=True, text=True, check=True)
            
            user_info = json.loads(get_user_result.stdout)
            username = user_info['User']['UserName']
            
            # Get access keys for the user
            list_keys_result = subprocess.run([
                'aws', 'iam', 'list-access-keys',
                '--profile', profile_name,
                '--user-name', username,
                '--output', 'json'
            ], capture_output=True, text=True, check=True)
            
            keys_info = json.loads(list_keys_result.stdout)
            access_keys = keys_info['AccessKeyMetadata']
            
            if not access_keys:
                print(f"✗ No access keys found for {profile_name}")
                return None
            
            # Get the current access key being used (from credentials file)
            current_profiles = self.get_aws_profiles()
            current_access_key_id = None
            for profile in current_profiles:
                if profile['name'] == profile_name:
                    current_access_key_id = profile['access_key_id']
                    break
            
            # Find the access key that matches current credentials
            current_key_info = None
            for key in access_keys:
                if key['AccessKeyId'] == current_access_key_id:
                    current_key_info = key
                    break
            
            if not current_key_info:
                print(f"⚠️ Current access key {current_access_key_id} not found in AWS (may be deleted)")
                return None
            
            # Calculate age
            create_date_str = current_key_info['CreateDate']
            if isinstance(create_date_str, str):
                # Parse ISO timestamp
                create_date = datetime.fromisoformat(create_date_str.replace('Z', '+00:00'))
            else:
                # create_date_str is already a datetime object
                create_date = create_date_str
            
            now = datetime.now(create_date.tzinfo) if create_date.tzinfo else datetime.now()
            age_days = (now - create_date).days
            
            return {
                'access_key_id': current_access_key_id,
                'username': username,
                'create_date': create_date_str,
                'age_days': age_days,
                'outdated': age_days >= 100,  # Default 100 days for access keys
                'status': current_key_info['Status'],
                'source': 'AWS API'
            }
            
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to get access key info for {profile_name}: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"✗ Failed to parse AWS response: {e}")
            return None
        except Exception as e:
            print(f"✗ Error checking access key age for {profile_name}: {e}")
            return None

    def list_outdated_access_keys(self, max_age_days=100):
        """List all profiles with outdated access keys"""
        if not self.check_op_session():
            return []
        
        outdated_profiles = []
        mapped_profiles = list(self.profile_mappings.keys())
        
        print(f"Checking access key age for {len(mapped_profiles)} mapped profiles...")
        print(f"Access key policy: {max_age_days} days maximum age\n")
        
        for profile_name in mapped_profiles:
            onepassword_title = self.get_1password_item_title(profile_name)
            access_key_info = self.get_access_key_age(profile_name)
            
            if access_key_info:
                # Update outdated status based on provided max_age_days
                access_key_info['outdated'] = access_key_info['age_days'] >= max_age_days
                
                status = "🔴 OUTDATED" if access_key_info['outdated'] else "🟢 OK"
                print(f"{status} {profile_name}")
                print(f"    1Password: {onepassword_title}")
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
                        'onepassword_title': onepassword_title,
                        **access_key_info
                    })
            else:
                print(f"⚠️  UNKNOWN {profile_name}")
                print(f"    1Password: {onepassword_title}")
                print(f"    Could not check access key age")
                print()
        
        print(f"Summary: {len(outdated_profiles)}/{len(mapped_profiles)} profiles have outdated access keys")
        return outdated_profiles

    def update_outdated_access_keys(self, max_age_days=100, dry_run=False):
        """Update all profiles with outdated access keys"""
        outdated_profiles = self.list_outdated_access_keys(max_age_days)
        
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
        
        # Proceed with updates
        print("\nProceeding to refresh outdated access keys...")
        
        success_count = 0
        for profile in outdated_profiles:
            profile_name = profile['profile_name']
            print(f"\n🔄 Refreshing {profile_name} (age: {profile['age_days']} days)...")
            print(f"  Current key: {profile['access_key_id']}")
            
            if self.refresh_access_key(profile_name, dry_run=False):
                success_count += 1
            else:
                print(f"❌ Failed to refresh {profile_name}")
        
        print(f"\n📊 Summary: {success_count}/{len(outdated_profiles)} outdated access keys refreshed successfully")
        return success_count == len(outdated_profiles)

    def update_all_credentials(self, password_max_age=90, access_key_max_age=90, dry_run=False):
        """Update both passwords and access keys for all profiles (quarterly maintenance)"""
        if not self.check_op_session():
            return False
        
        print("🔄 Starting quarterly credential update (passwords + access keys)")
        print(f"Password policy: {password_max_age} days maximum age")
        print(f"Access key policy: {access_key_max_age} days maximum age")
        print("=" * 60)
        
        # Step 1: Update expired passwords
        print("\n📍 Step 1: Updating expired passwords...")
        password_success = self.update_expired_passwords(password_max_age, dry_run)
        
        # Step 2: Update outdated access keys
        print("\n📍 Step 2: Updating outdated access keys...")
        access_key_success = self.update_outdated_access_keys(access_key_max_age, dry_run)
        
        # Summary
        print("\n" + "=" * 60)
        print("🎯 QUARTERLY CREDENTIAL UPDATE SUMMARY:")
        print(f"  Passwords: {'✅ Success' if password_success else '❌ Some failures'}")
        print(f"  Access Keys: {'✅ Success' if access_key_success else '❌ Some failures'}")
        
        overall_success = password_success and access_key_success
        print(f"  Overall: {'✅ Complete success!' if overall_success else '⚠️ Check logs for issues'}")
        
        if not dry_run:
            # Log the quarterly update
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'type': 'quarterly_update',
                'password_max_age': password_max_age,
                'access_key_max_age': access_key_max_age,
                'password_success': password_success,
                'access_key_success': access_key_success,
                'overall_success': overall_success
            }
            self._log_quarterly_update(log_entry)
        
        return overall_success

    def _log_quarterly_update(self, log_entry):
        """Log quarterly update results"""
        try:
            log_file = os.path.join(os.path.dirname(__file__), "quarterly_updates.log")
            with open(log_file, "a") as f:
                f.write(f"{json.dumps(log_entry)}\n")
            print(f"📝 Logged update to: {log_file}")
        except Exception as e:
            print(f"⚠️ Could not log quarterly update: {e}")

    def get_password_age(self, profile_name):
        """Get password age from 1Password timestamp"""
        return self.get_password_age_from_1password(profile_name)
    
    def list_expired_passwords(self, max_age_days=90):
        """List all profiles with expired passwords"""
        if not self.check_op_session():
            return []
        
        expired_profiles = []
        mapped_profiles = list(self.profile_mappings.keys())
        
        print(f"Checking password age for {len(mapped_profiles)} mapped profiles...")
        print(f"Password policy: {max_age_days} days maximum age\n")
        
        for profile_name in mapped_profiles:
            onepassword_title = self.get_1password_item_title(profile_name)
            password_info = self.get_password_age(profile_name)
            
            if password_info:
                status = "🔴 EXPIRED" if password_info['expired'] else "🟢 OK"
                print(f"{status} {profile_name}")
                print(f"    1Password: {onepassword_title}")
                
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
                        'onepassword_title': onepassword_title,
                        **password_info
                    })
            else:
                print(f"⚠️  UNKNOWN {profile_name}")
                print(f"    1Password: {onepassword_title}")
                print(f"    Could not check password age")
                print()
        
        print(f"Summary: {len(expired_profiles)}/{len(mapped_profiles)} profiles have expired passwords")
        return expired_profiles
    
    def update_expired_passwords(self, max_age_days=90, dry_run=False):
        """Update all profiles with expired passwords"""
        expired_profiles = self.list_expired_passwords(max_age_days)
        
        if not expired_profiles:
            print("✅ No expired passwords found!")
            return True
        
        print(f"\n🔄 Found {len(expired_profiles)} expired passwords")
        
        if dry_run:
            print("\n[DRY RUN] Would update the following expired passwords:")
            for profile in expired_profiles:
                print(f"  - {profile['profile_name']} (age: {profile['age_days']} days)")
            return True
        
        # Proceed with updates
        print("\nProceeding to update expired passwords...")
        
        success_count = 0
        for profile in expired_profiles:
            profile_name = profile['profile_name']
            print(f"\n🔄 Updating {profile_name} (age: {profile['age_days']} days)...")
            
            if self.update_profile(profile_name, dry_run=False):
                success_count += 1
            else:
                print(f"❌ Failed to update {profile_name}")
        
        print(f"\n📊 Summary: {success_count}/{len(expired_profiles)} expired passwords updated successfully")
        return success_count == len(expired_profiles)
    
    def import_aws_credentials_to_1password(self, profile_name=None, dry_run=False):
        """Import AWS access keys from credentials file to existing 1Password items"""
        if profile_name:
            # Import single profile
            profiles = self.get_aws_profiles()
            target_profiles = [p for p in profiles if p['name'] == profile_name]
            if not target_profiles:
                print(f"✗ Profile '{profile_name}' not found in AWS credentials")
                return False
        else:
            # Import all mapped profiles
            profiles = self.get_aws_profiles()
            target_profiles = [p for p in profiles if p['name'] in self.profile_mappings]
        
        if not target_profiles:
            print("✗ No profiles to import")
            return False
        
        print(f"Importing AWS credentials for {len(target_profiles)} profiles to 1Password...")
        
        success_count = 0
        for profile in target_profiles:
            profile_name = profile['name']
            onepassword_title = self.get_1password_item_title(profile_name)
            
            if not onepassword_title:
                print(f"⚠️ Skipping {profile_name}: No 1Password mapping found")
                continue
            
            if dry_run:
                print(f"[DRY RUN] Would import credentials for '{profile_name}':")
                print(f"  1Password Item: {onepassword_title}")
                print(f"  AWS Access Key ID: {profile['access_key_id']}")
                print(f"  AWS Secret Key: {profile['secret_access_key'][:8]}...")
                print()
                success_count += 1
                continue
            
            # Check if item exists
            try:
                result = subprocess.run([
                    'op', 'item', 'get', onepassword_title, '--vault', self.vault_name, '--format', 'json'
                ], capture_output=True, text=True, check=True)
                
                item_data = json.loads(result.stdout)
                
                # Check if AWS credential fields already exist
                has_access_key = False
                has_secret_key = False
                
                for field in item_data.get('fields', []):
                    if field.get('label') == 'aws_access_key_id':
                        has_access_key = True
                    elif field.get('label') == 'aws_secret_access_key':
                        has_secret_key = True
                
                # Add or update AWS credential fields
                subprocess.run([
                    'op', 'item', 'edit', onepassword_title,
                    '--vault', self.vault_name,
                    f'aws_access_key_id[text]={profile["access_key_id"]}',
                    f'aws_secret_access_key[password]={profile["secret_access_key"]}',
                    f'credential_import_date[text]={datetime.now().isoformat()}'
                ], check=True)
                
                action = "Updated" if (has_access_key or has_secret_key) else "Added"
                print(f"✓ {action} AWS credentials in 1Password: {onepassword_title}")
                success_count += 1
                
            except subprocess.CalledProcessError as e:
                print(f"✗ Failed to import credentials for {profile_name}: {e}")
            except json.JSONDecodeError as e:
                print(f"✗ Failed to parse 1Password item for {profile_name}: {e}")
        
        print(f"\n📊 Summary: {success_count}/{len(target_profiles)} profiles imported successfully")
        return success_count == len(target_profiles)
    
    def update_profile(self, profile_name, dry_run=False):
        """Update AWS console password and store in 1Password"""
        # Check if profile mapping exists
        onepassword_title = self.get_1password_item_title(profile_name)
        if not onepassword_title:
            print(f"✗ No 1Password mapping found for profile: {profile_name}")
            return False
        
        if dry_run:
            print(f"[DRY RUN] Would update AWS console password for '{profile_name}':")
            print(f"  1Password Item: {onepassword_title}")
            print(f"  Actions:")
            print(f"    1. Generate secure password (18+ chars, meets AWS policy)")
            print(f"    2. Update AWS console password via IAM API")
            print(f"    3. Store new password in 1Password")
            return True
        
        # First check if AWS credentials are valid
        try:
            test_result = subprocess.run([
                'aws', 'iam', 'get-user',
                '--profile', profile_name,
                '--output', 'json'
            ], capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            print(f"⚠️ Skipping {profile_name}: Invalid AWS credentials")
            if e.stderr:
                error_msg = e.stderr.decode().strip() if isinstance(e.stderr, bytes) else str(e.stderr).strip()
                if "InvalidClientTokenId" in error_msg:
                    print(f"  Reason: AWS access keys are expired or invalid")
                else:
                    print(f"  Reason: {error_msg}")
            print(f"  Note: Fix AWS credentials for {profile_name} to enable password updates")
            return False
        
        # Generate password using fallback method to get the actual password
        new_password = self._fallback_password_generation(18)
        
        # Update AWS console password
        if not self.update_aws_console_password(profile_name, new_password):
            return False
        
        # Then update 1Password with the same password
        if not self.update_1password_item_with_password(profile_name, new_password):
            return False
        
        print(f"✓ Successfully updated both AWS and 1Password for: {profile_name}")
        return True
    
    def update_all_profiles(self, dry_run=False):
        """Update all mapped AWS profiles in 1Password"""
        if not self.check_op_session():
            return False
        
        # Only process profiles that have 1Password mappings
        mapped_profiles = []
        for profile_name in self.profile_mappings.keys():
            mapped_profiles.append(profile_name)
        
        print(f"Found {len(mapped_profiles)} mapped AWS profiles")
        
        success_count = 0
        for profile_name in mapped_profiles:
            if self.update_profile(profile_name, dry_run):
                success_count += 1
            print()  # Empty line for readability
        
        print(f"Summary: {success_count}/{len(mapped_profiles)} profiles updated successfully")
        return success_count == len(mapped_profiles)
    
    def generate_mapping_file(self, output_file=None, interactive=True):
        """Generate profile mapping file from existing AWS profiles"""
        output_file = output_file or "profile_mapping.json"
        
        print("🔍 Scanning for AWS profiles...")
        try:
            profiles = self.get_aws_profiles()
        except FileNotFoundError:
            print("✗ AWS credentials file not found. Please configure AWS CLI first.")
            print("  Run: aws configure --profile <profile-name>")
            return False
        
        if not profiles:
            print("✗ No AWS profiles found in credentials file")
            return False
        
        print(f"Found {len(profiles)} AWS profiles:")
        for i, profile in enumerate(profiles, 1):
            print(f"  {i}. {profile['name']}")
        
        mapping_data = {
            "profile_mappings": {},
            "notes": {
                "usage": "This file maps AWS credential profile names to their corresponding 1Password item titles",
                "format": "profile_name -> {onepassword_title, description}",
                "generated_on": datetime.now().isoformat(),
                "auto_generated": True
            }
        }
        
        if interactive:
            print("\n📝 Creating mappings (press Enter to skip a profile):")
            
            for profile in profiles:
                profile_name = profile['name']
                print(f"\n🔹 Profile: {profile_name}")
                
                # Suggest 1Password title based on profile name
                suggested_title = self._suggest_1password_title(profile_name)
                onepassword_title = input(f"  1Password item title [{suggested_title}]: ").strip()
                onepassword_title = onepassword_title or suggested_title
                
                description = input(f"  Description [AWS environment for {profile_name}]: ").strip()
                description = description or f"AWS environment for {profile_name}"
                
                if onepassword_title:
                    mapping_data["profile_mappings"][profile_name] = {
                        "onepassword_title": onepassword_title,
                        "description": description
                    }
                    print(f"  ✓ Added mapping for {profile_name}")
                else:
                    print(f"  ⏭ Skipped {profile_name}")
        else:
            # Non-interactive mode - generate with suggested names
            print("\n🤖 Auto-generating mappings...")
            for profile in profiles:
                profile_name = profile['name']
                suggested_title = self._suggest_1password_title(profile_name)
                description = f"AWS environment for {profile_name}"
                
                mapping_data["profile_mappings"][profile_name] = {
                    "onepassword_title": suggested_title,
                    "description": description
                }
                print(f"  ✓ Generated mapping for {profile_name}")
        
        # Write the mapping file
        try:
            with open(output_file, 'w') as f:
                json.dump(mapping_data, f, indent=2)
            
            mapped_count = len(mapping_data["profile_mappings"])
            print(f"\n✅ Generated mapping file: {output_file}")
            print(f"   Mapped {mapped_count}/{len(profiles)} profiles")
            
            if mapped_count < len(profiles):
                skipped = len(profiles) - mapped_count
                print(f"   Skipped {skipped} profiles (you can add them later)")
            
            print(f"\n📋 Next steps:")
            print(f"   1. Review and edit {output_file}")
            print(f"   2. Ensure 1Password items exist with exact titles")
            print(f"   3. Test with: python3 aws_credential_updater.py list")
            
            return True
            
        except Exception as e:
            print(f"✗ Failed to write mapping file: {e}")
            return False
    
    def _suggest_1password_title(self, profile_name):
        """Suggest a 1Password title based on AWS profile name"""
        # Convert profile name to a more readable format
        # Examples:
        # company-service-dev -> AWS Company Service Dev
        # my-project-prod -> AWS My Project Prod
        
        parts = profile_name.replace('_', '-').split('-')
        title_parts = []
        
        for part in parts:
            # Capitalize each part
            if part.lower() in ['dev', 'development']:
                title_parts.append('Dev')
            elif part.lower() in ['prod', 'production']:
                title_parts.append('Prod')
            elif part.lower() in ['staging', 'stage']:
                title_parts.append('Staging')
            elif part.lower() in ['test', 'testing']:
                title_parts.append('Test')
            else:
                title_parts.append(part.title())
        
        return f"AWS {' '.join(title_parts)}"
    
    def list_profiles(self):
        """List all AWS profiles"""
        profiles = self.get_aws_profiles()
        print(f"Found {len(profiles)} AWS profiles:")
        for i, profile in enumerate(profiles, 1):
            profile_name = profile['name']
            onepassword_title = self.get_1password_item_title(profile_name)
            status = "✓ Mapped" if onepassword_title else "✗ Not mapped"
            
            print(f"{i:2d}. {profile_name}")
            print(f"     Access Key: {profile['access_key_id']}")
            print(f"     1Password: {onepassword_title or 'No mapping found'} ({status})")
            print()

def main():
    import argparse
    
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
    expired_parser.add_argument('--max-age', type=int, default=90, 
                               help='Maximum password age in days (default: 90)')
    
    # Update expired passwords
    update_expired_parser = subparsers.add_parser('update-expired', help='Update all expired passwords')
    update_expired_parser.add_argument('--max-age', type=int, default=90,
                                      help='Maximum password age in days (default: 90)')
    
    # Import credentials
    import_parser = subparsers.add_parser('import-credentials', help='Import AWS credentials to 1Password')
    import_parser.add_argument('profile_name', nargs='?', help='Profile name to import (optional, imports all if not specified)')
    
    # Import all credentials
    subparsers.add_parser('import-all-credentials', help='Import all AWS credentials to 1Password')
    
    # Refresh access key for single profile
    refresh_parser = subparsers.add_parser('refresh-access-key', help='Refresh (recreate) AWS access key for a specific profile')
    refresh_parser.add_argument('profile_name', help='Name of the profile to refresh access key for')
    
    # Refresh access keys for all profiles
    subparsers.add_parser('refresh-all-access-keys', help='Refresh access keys for all mapped profiles')
    
    # List outdated access keys
    outdated_keys_parser = subparsers.add_parser('list-outdated-access-keys', help='List profiles with outdated access keys')
    outdated_keys_parser.add_argument('--max-age', type=int, default=100,
                                     help='Maximum access key age in days (default: 100)')
    
    # Update outdated access keys
    update_outdated_keys_parser = subparsers.add_parser('update-outdated-access-keys', help='Update all outdated access keys')
    update_outdated_keys_parser.add_argument('--max-age', type=int, default=100,
                                             help='Maximum access key age in days (default: 100)')
    
    # Quarterly update - combined password and access key updates
    quarterly_parser = subparsers.add_parser('quarterly-update', help='Update both passwords and access keys (for scheduled maintenance)')
    quarterly_parser.add_argument('--password-max-age', type=int, default=90,
                                  help='Maximum password age in days (default: 90)')
    quarterly_parser.add_argument('--access-key-max-age', type=int, default=90,
                                  help='Maximum access key age in days (default: 90)')
    
    # Generate mapping file
    generate_parser = subparsers.add_parser('generate-mapping', help='Generate profile mapping file from existing AWS profiles')
    generate_parser.add_argument('--output', default='profile_mapping.json',
                                help='Output file name (default: profile_mapping.json)')
    generate_parser.add_argument('--non-interactive', action='store_true',
                                help='Generate mappings automatically without prompts')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    updater = AWSCredentialUpdater(args.credentials_path, args.vault)
    
    try:
        if args.command == 'list':
            updater.list_profiles()
        elif args.command == 'update':
            if not updater.check_op_session():
                return 1
            updater.update_profile(args.profile_name, args.dry_run)
        elif args.command == 'update-all':
            updater.update_all_profiles(args.dry_run)
        elif args.command == 'list-expired':
            updater.list_expired_passwords(args.max_age)
        elif args.command == 'update-expired':
            if not updater.check_op_session():
                return 1
            updater.update_expired_passwords(args.max_age, args.dry_run)
        elif args.command == 'import-credentials':
            if not updater.check_op_session():
                return 1
            profile_name = getattr(args, 'profile_name', None)
            updater.import_aws_credentials_to_1password(profile_name, args.dry_run)
        elif args.command == 'import-all-credentials':
            if not updater.check_op_session():
                return 1
            updater.import_aws_credentials_to_1password(None, args.dry_run)
        elif args.command == 'refresh-access-key':
            if not updater.check_op_session():
                return 1
            updater.refresh_access_key(args.profile_name, args.dry_run)
        elif args.command == 'refresh-all-access-keys':
            if not updater.check_op_session():
                return 1
            updater.refresh_all_access_keys(args.dry_run)
        elif args.command == 'list-outdated-access-keys':
            if not updater.check_op_session():
                return 1
            updater.list_outdated_access_keys(args.max_age)
        elif args.command == 'update-outdated-access-keys':
            if not updater.check_op_session():
                return 1
            updater.update_outdated_access_keys(args.max_age, args.dry_run)
        elif args.command == 'quarterly-update':
            if not updater.check_op_session():
                return 1
            updater.update_all_credentials(args.password_max_age, args.access_key_max_age, args.dry_run)
        elif args.command == 'generate-mapping':
            # Don't require 1Password session for mapping generation
            updater.generate_mapping_file(args.output, not args.non_interactive)
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())