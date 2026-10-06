# AWS Credential Manager

[![CI](https://github.com/nguyenquangkhai/aws-credential-manage/actions/workflows/ci.yml/badge.svg)](https://github.com/nguyenquangkhai/aws-credential-manage/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](pyproject.toml)
[![Code style: ruff](https://img.shields.io/badge/lint-ruff-261230.svg)](https://github.com/astral-sh/ruff)

A comprehensive tool for automating AWS IAM credential management, integrating with 1Password or Bitwarden for secure password storage and featuring automatic quarterly maintenance.

## Features

### 🔐 Password Management
- Update AWS console passwords for IAM users
- Track password age and enforce 90-day rotation policy
- Secure password generation meeting AWS requirements
- 1Password or Bitwarden integration for centralized storage

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
- 1Password CLI (`op`) **or** Bitwarden CLI (`bw`)
- AWS CLI configured with profiles
- macOS (for automation features)

### Installation
1. Clone this repository
2. Configure your profile mappings in `profile_mapping.json`
3. (Optional) Copy `.env.example` to `.env` to configure per-machine settings
4. Set up automation: `./setup_quarterly_automation.sh`

### Environment Configuration (`.env`)
Copy `.env.example` to `.env` to configure per-machine settings. Precedence:
real environment variable > `.env` file > built-in default.
- `DEFAULT_VAULT` — vault name (built-in default: `AWS`)
- `DEFAULT_VAULT_TYPE` — vault backend: `1password` or `bitwarden` (built-in default: `1password`)
- `PROFILE_MAPPING_FILE` — profile mapping file; relative paths resolve
  against the project root (built-in default: `profile_mapping.json`)

### Basic Usage

**1Password (default):**
```bash
# List all profiles
aws-credential-manager list

# Update specific profile password
aws-credential-manager update <profile_name>

# Refresh access key for profile
aws-credential-manager refresh-access-key <profile_name>

# Quarterly maintenance (both passwords and keys)
aws-credential-manager quarterly-update
```

**Bitwarden:**
```bash
# Unlock vault and export session
export BW_SESSION=$(bw unlock --raw)

# List all profiles
aws-credential-manager --vault-type bitwarden list

# Update specific profile password
aws-credential-manager --vault-type bitwarden update <profile_name>

# Import existing AWS access keys from ~/.aws/credentials into Bitwarden
aws-credential-manager --vault-type bitwarden import-all-credentials
```

**Set Bitwarden as default (via `.env` or environment):**
```
DEFAULT_VAULT_TYPE=bitwarden
```
Then omit `--vault-type` from all commands.

## Documentation

See [CLAUDE.md](CLAUDE.md) for comprehensive usage documentation, including:
- Complete command reference
- Configuration instructions  
- Automation setup guide
- Security considerations

## Architecture

- **Main Script**: `aws_credential_updater.py` - Core functionality
- **Configuration**: `profile_mapping.json` - AWS profile to vault item mappings
- **Automation**: macOS Launch Agent with quarterly scheduling
- **Logging**: Comprehensive audit trail with email notifications

## Security

- Access keys stored only in `~/.aws/credentials` (not in vault)
- Automatic credential backup before changes
- Comprehensive error handling with rollback capabilities
- No secrets logged or exposed in error messages

## Development

```bash
# Install with dev tooling
pip install -e ".[dev]"

# Run the test suite (with coverage)
pytest

# Lint and type-check
ruff check .
mypy aws_credential_manager
```

CI runs lint, type-check, and tests on Python 3.11–3.13 for every push and
pull request. See [.github/workflows/ci.yml](.github/workflows/ci.yml).

## License

MIT License - See [LICENSE](LICENSE) file for details.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All changes should include appropriate
tests and pass CI. Report security issues per [SECURITY.md](SECURITY.md).