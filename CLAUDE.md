# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AWS credential management tool that automates the process of updating AWS IAM user console passwords and synchronizing them with 1Password. The tool helps maintain security compliance by rotating passwords based on age policies and keeping credentials centralized.

## Core Architecture

- **Main Script**: `aws_credential_updater.py` - Single-file Python application with CLI interface
- **Configuration**: `profile_mapping.json` - Maps AWS profile names to corresponding 1Password item titles
- **Runtime**: Uses `mise.toml` for Python 3.13 version management

## Key Components

### AWSCredentialUpdater Class
Located in `aws_credential_updater.py`, this class handles:
- AWS credentials file parsing (~/.aws/credentials)
- 1Password CLI integration via `op` commands
- AWS IAM API calls for password updates and access key management
- Secure password generation (18+ chars, meets AWS policy)
- Password age tracking and expiry management (90-day default)
- Access key refresh (creation, rotation, deletion)
- Access key age tracking and outdated key detection (100-day default)

### Profile Mapping System
The `profile_mapping.json` file maintains mappings between:
- AWS credential profile names (e.g., "resola-deca-chatbot-dev")
- 1Password item titles (e.g., "AWS Deca Chatbot Dev")
- Environment descriptions

## Common Commands

### Basic Operations
```bash
# List all AWS profiles with their 1Password mappings
python3 aws_credential_updater.py list

# Update a specific profile's password
python3 aws_credential_updater.py update <profile_name>

# Update all mapped profiles
python3 aws_credential_updater.py update-all

# Show what would be updated without making changes
python3 aws_credential_updater.py --dry-run <command>
```

### Password Management
```bash
# List profiles with expired passwords (>90 days)
python3 aws_credential_updater.py list-expired

# Update all expired passwords
python3 aws_credential_updater.py update-expired

# Set custom age threshold (e.g., 60 days)
python3 aws_credential_updater.py list-expired --max-age 60
```

### Credential Import
```bash
# Import AWS access keys to 1Password for all mapped profiles
python3 aws_credential_updater.py import-all-credentials

# Import credentials for a specific profile
python3 aws_credential_updater.py import-credentials <profile_name>
```

### Access Key Refresh
```bash
# Refresh (recreate) AWS access key for a specific profile
python3 aws_credential_updater.py refresh-access-key <profile_name>

# Refresh access keys for all mapped profiles
python3 aws_credential_updater.py refresh-all-access-keys

# Show what would be refreshed without making changes
python3 aws_credential_updater.py --dry-run refresh-access-key <profile_name>
```

### Outdated Access Key Management
```bash
# List profiles with outdated access keys (>100 days)
python3 aws_credential_updater.py list-outdated-access-keys

# Update all outdated access keys
python3 aws_credential_updater.py update-outdated-access-keys

# Set custom age threshold (e.g., 60 days)
python3 aws_credential_updater.py list-outdated-access-keys --max-age 60

# Show what would be updated without making changes
python3 aws_credential_updater.py --dry-run update-outdated-access-keys
```

### Quarterly Maintenance
```bash
# Combined update of both passwords and access keys (ideal for scheduled maintenance)
python3 aws_credential_updater.py quarterly-update

# Customize age thresholds for quarterly update
python3 aws_credential_updater.py quarterly-update --password-max-age 90 --access-key-max-age 90

# Test quarterly update without making changes
python3 aws_credential_updater.py --dry-run quarterly-update
```

## Dependencies and Prerequisites

### Required Tools
- **1Password CLI**: Must be installed and authenticated (`op signin`)
- **AWS CLI**: Required for IAM operations (`aws configure` for each profile)
- **Python 3.13**: Managed via mise

### Authentication Requirements
- 1Password CLI session must be active
- AWS credentials must be valid for each profile being updated
- IAM permissions required: 
  - For password updates: `iam:GetUser`, `iam:UpdateLoginProfile`
  - For access key refresh: `iam:CreateAccessKey`, `iam:DeleteAccessKey`, `iam:ListAccessKeys`
  - For access key age tracking: `iam:GetUser`, `iam:ListAccessKeys`

## Configuration Notes

### Adding New AWS Profiles
1. Add AWS credentials to `~/.aws/credentials`
2. Create corresponding 1Password item in the "AWS" vault
3. Add mapping entry in `profile_mapping.json`:
   ```json
   "profile-name": {
     "onepassword_title": "1Password Item Title",
     "description": "Environment description"
   }
   ```

### Vault Configuration
- Default 1Password vault: "AWS"
- Override with `--vault` flag
- All 1Password items must exist in the specified vault

## Security Considerations

- Passwords meet AWS policy: 18+ characters, mixed case, numbers, symbols
- No credentials are logged or stored in plaintext
- All password operations use secure generation methods
- Failed operations don't expose sensitive data in error messages
- Access keys are stored only in `~/.aws/credentials` (not in 1Password)
- Access key refresh creates backup files automatically before making changes
- AWS 2-key limit enforced: refresh fails if user already has 2 active keys
- Comprehensive rollback mechanisms in case of refresh failures
- Access key age tracked via AWS API (not 1Password) for accurate timestamps
- Outdated access key detection helps maintain compliance with rotation policies

## Automated Scheduling (macOS)

The tool includes macOS automation for quarterly credential maintenance using Launch Agents.

### Setup Automation
```bash
# One-time setup to install the quarterly automation
./setup_quarterly_automation.sh
```

### Schedule Details
- **Frequency**: Every 3 months (Jan 1, Apr 1, Jul 1, Oct 1)
- **Time**: 9:00 AM
- **Actions**: Updates both expired passwords (>90 days) and outdated access keys (>90 days)
- **Logging**: Automatic logging to `logs/` directory
- **Notifications**: Optional email notifications (configure in plist file)

### Manual Commands
```bash
# Test the automation setup
./aws_quarterly_update.sh test

# Run a dry-run to see what would be updated
./aws_quarterly_update.sh dry-run

# Run the quarterly update immediately
./aws_quarterly_update.sh

# View recent logs
tail -f logs/launchd.log
```

### Management Commands
```bash
# Check if automation is running
launchctl list | grep com.resola.aws-credential-updater

# Stop the automation
launchctl unload ~/Library/LaunchAgents/com.resola.aws-credential-updater.plist

# Start the automation
launchctl load ~/Library/LaunchAgents/com.resola.aws-credential-updater.plist
```

### Email Notifications
To enable email notifications:
1. Edit `~/Library/LaunchAgents/com.resola.aws-credential-updater.plist`
2. Change `<string>your-email@example.com</string>` to your actual email
3. Ensure `mail` command is configured on your system
4. Reload: `launchctl unload <plist> && launchctl load <plist>`