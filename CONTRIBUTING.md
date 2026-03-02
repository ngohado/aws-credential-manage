# Contributing to AWS Credential Manager

Thank you for your interest in contributing to AWS Credential Manager! This document provides guidelines and information for contributors.

## 🤝 How to Contribute

### Reporting Bugs
1. **Check existing issues** first to avoid duplicates
2. **Use the bug report template** when creating new issues
3. **Provide detailed information**:
   - Operating system and version
   - Python version
   - AWS CLI version
   - 1Password CLI version
   - Steps to reproduce
   - Expected vs actual behavior
   - Error messages and logs

### Suggesting Features
1. **Check existing feature requests** first
2. **Use the feature request template**
3. **Explain the use case** and why it would be valuable
4. **Consider implementation complexity** and backwards compatibility

### Contributing Code

#### Prerequisites
- Python 3.11+
- 1Password CLI
- AWS CLI
- macOS (for automation features)
- Git

#### Development Setup

**Modern workflow with `uv` (recommended):**
```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone your fork
git clone https://github.com/yourusername/aws-credential-manager.git
cd aws-credential-manager

# Setup development environment (creates venv automatically)
uv sync --dev

# Install pre-commit hooks
uv run pre-commit install
```

**Traditional workflow (if you prefer):**
```bash
# Clone your fork
git clone https://github.com/yourusername/aws-credential-manager.git
cd aws-credential-manager

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install development dependencies  
pip install -e ".[dev,test]"

# Install pre-commit hooks
pre-commit install
```

#### Making Changes
1. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Write tests** for your changes:
   - Unit tests in `tests/unit/`
   - Integration tests in `tests/integration/`
   - Follow existing test patterns

3. **Follow code style**:
   ```bash
   # Modern workflow with uv
   uv run ruff format .      # Format code
   uv run ruff check .       # Lint code  
   uv run mypy .            # Type checking
   
   # Traditional workflow
   ruff format .
   ruff check .
   mypy .
   ```

4. **Test your changes**:
   ```bash
   # Modern workflow with uv
   uv run pytest                    # Run all tests
   uv run pytest --cov             # Run with coverage
   uv run python aws_credential_updater.py --dry-run quarterly-update
   
   # Traditional workflow  
   pytest
   pytest --cov=aws_credential_updater
   python aws_credential_updater.py --dry-run quarterly-update
   ```

5. **Update documentation**:
   - Update `README.md` if needed
   - Update `CLAUDE.md` for new features
   - Add docstrings to new functions
   - Update help text for new CLI commands

6. **Commit your changes**:
   ```bash
   git add .
   git commit -m "feat: add new feature description"
   ```
   Use [Conventional Commits](https://www.conventionalcommits.org/) format.

#### Pull Request Process
1. **Update your branch** with latest main:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

3. **Create pull request**:
   - Use the PR template
   - Link related issues
   - Provide clear description of changes
   - Add screenshots/demos if applicable

4. **Code review process**:
   - Maintainers will review your PR
   - Address feedback promptly
   - Keep discussions constructive

## 🧪 Testing Guidelines

### Test Structure
```
tests/
├── unit/           # Fast, isolated tests
├── integration/    # End-to-end tests
├── fixtures/       # Test data
└── conftest.py     # Shared test configuration
```

### Writing Tests
- Use descriptive test names
- Test both success and failure cases
- Mock external dependencies (AWS, 1Password)
- Use pytest fixtures for common setup

### Test Coverage
- Aim for 90%+ code coverage
- Focus on critical security and credential handling code
- Include edge cases and error conditions

## 🔒 Security Considerations

### Security-First Development
- **Never log credentials** or sensitive data
- **Validate all inputs** to prevent injection attacks
- **Use secure defaults** for all configurations
- **Follow principle of least privilege**

### Credential Handling
- AWS credentials should only exist in `~/.aws/credentials`
- 1Password integration should use official CLI only
- No credentials should ever be committed to git
- Test with dummy/mock credentials only

### Reporting Security Issues
- **Do not open public issues** for security vulnerabilities
- Email security@[domain] with details
- Use GPG encryption if possible
- Follow responsible disclosure principles

## 📝 Documentation Standards

### Code Documentation
- Use clear, descriptive function and variable names
- Add docstrings to all public functions
- Include type hints for function parameters and returns
- Comment complex logic and business rules

### User Documentation
- Update README.md for user-facing changes
- Update CLAUDE.md for new CLI commands
- Include examples and use cases
- Keep documentation current with code changes

## 🏷️ Release Process

### Versioning
- Use [Semantic Versioning](https://semver.org/)
- Major: Breaking changes
- Minor: New features, backwards compatible
- Patch: Bug fixes, backwards compatible

### Release Steps
1. Update version in `setup.py` and `__init__.py`
2. Update CHANGELOG.md
3. Create release PR
4. Tag release after merge
5. Update GitHub release notes

## 💬 Communication

### Community Guidelines
- Be respectful and inclusive
- Provide constructive feedback
- Help newcomers get started
- Share knowledge and best practices

### Getting Help
- Check documentation first
- Search existing issues
- Ask questions in discussions
- Be specific about your environment and use case

## 📄 License

By contributing to this project, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to AWS Credential Manager! 🎉