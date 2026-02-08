"""API key utilities.

Provides generation and verification for API keys.
"""

import secrets
import hashlib
from typing import Tuple


# API key format: sk-{random 32 bytes hex}
API_KEY_PREFIX = "sk-"
API_KEY_LENGTH = 32  # bytes (64 hex chars)


def generate_api_key() -> Tuple[str, str, str]:
    """Generate a new API key.

    Returns:
        Tuple of (full_key, key_hash, key_prefix).
        The full_key should be shown to the user once and never stored.
        The key_hash should be stored in the database.
        The key_prefix (first 8 chars after sk-) is for identification.
    """
    # Generate random bytes
    random_bytes = secrets.token_hex(API_KEY_LENGTH)

    # Create the full key
    full_key = f"{API_KEY_PREFIX}{random_bytes}"

    # Create prefix for identification (first 8 chars after sk-)
    key_prefix = f"sk-{random_bytes[:8]}"

    # Hash the key for storage
    key_hash = hash_api_key(full_key)

    return full_key, key_hash, key_prefix


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage.

    Uses SHA-256 for fast verification (API keys are already high entropy).

    Args:
        api_key: The full API key.

    Returns:
        SHA-256 hash of the key.
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key_hash(api_key: str, stored_hash: str) -> bool:
    """Verify an API key against its stored hash.

    Args:
        api_key: The API key to verify.
        stored_hash: The stored hash to check against.

    Returns:
        True if the key matches, False otherwise.
    """
    computed_hash = hash_api_key(api_key)
    # Use constant-time comparison to prevent timing attacks
    return secrets.compare_digest(computed_hash, stored_hash)


def extract_key_prefix(api_key: str) -> str:
    """Extract the prefix from an API key.

    Args:
        api_key: The full API key.

    Returns:
        The key prefix (first 8 chars after sk-).
    """
    if not api_key.startswith(API_KEY_PREFIX):
        return ""

    key_body = api_key[len(API_KEY_PREFIX):]
    return f"sk-{key_body[:8]}"


def is_valid_api_key_format(api_key: str) -> bool:
    """Check if an API key has a valid format.

    Args:
        api_key: The API key to validate.

    Returns:
        True if format is valid, False otherwise.
    """
    if not api_key.startswith(API_KEY_PREFIX):
        return False

    key_body = api_key[len(API_KEY_PREFIX):]

    # Should be 64 hex characters (32 bytes)
    if len(key_body) != API_KEY_LENGTH * 2:
        return False

    # Should be valid hex
    try:
        int(key_body, 16)
        return True
    except ValueError:
        return False
