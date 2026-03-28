"""Input validation utilities."""

import re
from typing import Optional


def validate_profile_name(profile_name: str) -> bool:
    """Validate AWS profile name format."""
    if not profile_name or not isinstance(profile_name, str):
        return False
    
    # AWS profile names should be reasonable length and characters
    if len(profile_name) > 100:
        return False
    
    # Allow alphanumeric, hyphens, underscores, dots
    pattern = r'^[a-zA-Z0-9._-]+$'
    return bool(re.match(pattern, profile_name))


def validate_age_threshold(age_days: int) -> bool:
    """Validate age threshold is reasonable."""
    if not isinstance(age_days, int):
        return False
    
    # Age should be between 1 and 1095 days (3 years)
    return 1 <= age_days <= 1095


def validate_email(email: Optional[str]) -> bool:
    """Validate email format."""
    if not email:
        return True  # Email is optional
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe file operations."""
    # Remove or replace dangerous characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Limit length
    if len(sanitized) > 255:
        sanitized = sanitized[:255]
    return sanitized