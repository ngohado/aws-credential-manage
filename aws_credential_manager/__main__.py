"""Allow running as: python -m aws_credential_manager"""

import sys
from .cli.main import main

sys.exit(main())
