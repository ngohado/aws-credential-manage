# Tests + Open Source Standard — Design

**Date:** 2026-06-30
**Status:** Approved

## Goal

Add a test suite and bring the repo up to open source standard: CI,
security fix, corrected config, and standard community files.

## Scope

### 1. Test suite (`tests/`)

Pytest-based. No real AWS or 1Password calls — subprocess mocked via
`pytest-mock`. Focus on core logic first; manager orchestration deferred.

- `tests/conftest.py` — shared fixtures: temporary AWS credentials ini
  file, mock subprocess helpers.
- `tests/test_validators.py` — `validate_profile_name`,
  `validate_age_threshold`, `validate_email`, `sanitize_filename`.
  Edge cases: empty, over-length, invalid chars, non-string, optional email.
- `tests/test_config.py` — `ConfigManager.get_aws_profiles`: parses ini,
  skips sections without `aws_access_key_id`, raises `FileNotFoundError`
  when the credentials file is missing; honors custom `vault_name`.
- `tests/test_onepassword.py` — `generate_password` (correct length, all
  char classes present, distinct outputs), `get_field_value` (found /
  missing / empty fields), and subprocess wrappers (`check_session`,
  `get_item`, `edit_item`, `edit_item_generate_password`) verifying command
  construction and returncode → `None` behavior.
- `tests/test_aws_client.py` — IAM wrapper methods with mocked subprocess:
  argument construction and error paths.

Target: strong coverage of `utils/` and `integrations/`.

### 2. CI (`.github/workflows/ci.yml`)

- Triggers: `push` and `pull_request`.
- Matrix: Python 3.11, 3.12, 3.13.
- Steps: install `.[dev]` → `ruff check .` → `mypy aws_credential_manager`
  → `pytest --cov`.
- Upload coverage XML as artifact.

### 3. Security fix

`OnePasswordClient.generate_password` uses the `random` module, which is
not cryptographically secure. Replace with `secrets` (use
`secrets.choice`; shuffle via a `secrets`-backed Fisher–Yates). Behavior
and signature unchanged.

### 4. Config fix

`pyproject.toml` coverage targets the near-dead wrapper
`aws_credential_updater`. Repoint to the package:

- `[tool.pytest.ini_options].addopts`: `--cov=aws_credential_manager`
- `[tool.coverage.run].source`: `["aws_credential_manager"]`

### 5. OSS community files

- `CHANGELOG.md` — Keep a Changelog format.
- `.github/ISSUE_TEMPLATE/bug_report.md`, `feature_request.md`.
- `.github/PULL_REQUEST_TEMPLATE.md`.
- `SECURITY.md` — reporting policy.
- `CODE_OF_CONDUCT.md` — Contributor Covenant.
- `README.md` — CI / license / python-version badges.

## Out of scope

- Manager-layer tests (`core/*_manager.py` orchestration).
- Real integration tests against AWS / 1Password.
- Docs site (mkdocs).
- Reconciling the 70-vs-90 day default-threshold drift between
  `config.py` and the docs (noted, not fixed in this pass).

## Success criteria

- `pytest` passes locally with meaningful coverage on `utils/` +
  `integrations/`.
- `ruff check .` and `mypy aws_credential_manager` pass.
- CI workflow present and green on push/PR.
- Community files present; README shows badges.
