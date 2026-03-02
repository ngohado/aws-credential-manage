# AWS Credential Manager

A comprehensive tool for automating AWS IAM credential management, integrating with 1Password for secure password storage and featuring automatic quarterly maintenance.

## Features

### 🔐 Password Management
- Update AWS console passwords for IAM users
- Track password age and enforce 90-day rotation policy
- Secure password generation meeting AWS requirements
- 1Password integration for centralized storage

### 🔑 Access Key Management  
- Refresh (recreate) AWS access keys with automatic rotation
- Track access key age and detect outdated keys (100-day policy)
- Safe rotation with backup and rollback mechanisms
- AWS 2-key limit enforcement

### 🤖 Automated Maintenance
- Quarterly automation using macOS Launch Agents
- Combined password and access key updates
- Comprehensive logging and email notifications
- One-command setup with testing capabilities

## Quick Start

### Prerequisites
- Python 3.13+ (managed via mise)
- 1Password CLI (`op`)
- AWS CLI configured with profiles
- macOS (for automation features)

### Installation
1. Clone this repository
2. Configure your profile mappings in `profile_mapping.json`
3. Set up automation: `./setup_quarterly_automation.sh`

### Basic Usage
```bash
# List all profiles
python3 aws_credential_updater.py list

# Update specific profile password
python3 aws_credential_updater.py update <profile_name>

# Refresh access key for profile
python3 aws_credential_updater.py refresh-access-key <profile_name>

# Quarterly maintenance (both passwords and keys)
python3 aws_credential_updater.py quarterly-update
```

## Documentation

See [CLAUDE.md](CLAUDE.md) for comprehensive usage documentation, including:
- Complete command reference
- Configuration instructions  
- Automation setup guide
- Security considerations

## Architecture

- **Main Script**: `aws_credential_updater.py` - Core functionality
- **Configuration**: `profile_mapping.json` - AWS profile to 1Password mappings
- **Automation**: macOS Launch Agent with quarterly scheduling
- **Logging**: Comprehensive audit trail with email notifications

## Security

- Access keys stored only in `~/.aws/credentials` (not in 1Password)
- Automatic credential backup before changes
- Comprehensive error handling with rollback capabilities
- No secrets logged or exposed in error messages

## License

MIT License - See LICENSE file for details.

## Contributing

Please read the contributing guidelines and ensure all changes include appropriate tests and documentation updates.