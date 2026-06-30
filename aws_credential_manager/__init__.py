"""AWS Credential Manager

A comprehensive tool for automating AWS IAM credential management
with 1Password integration and quarterly maintenance automation.
"""

__version__ = "1.0.0"
__author__ = "Khai Nguyen"
__email__ = "nguyenquangkhai@example.com"

from .core.credential_manager import CredentialManager

__all__ = ["CredentialManager", "__version__"]
