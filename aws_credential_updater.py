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
