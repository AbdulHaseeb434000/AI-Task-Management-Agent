"""Authentication module.

Provides JWT authentication, API key validation, and password hashing.
"""

from src.auth.jwt import (
    create_access_token,
    create_refresh_token,
    verify_token,
    TokenData,
)
from src.auth.password import (
    hash_password,
    verify_password,
)
from src.auth.dependencies import (
    get_current_user,
    get_current_active_user,
    get_optional_user,
    verify_api_key,
)
from src.auth.api_keys import (
    generate_api_key,
    hash_api_key,
    verify_api_key_hash,
)

__all__ = [
    # JWT
    "create_access_token",
    "create_refresh_token",
    "verify_token",
    "TokenData",
    # Password
    "hash_password",
    "verify_password",
    # Dependencies
    "get_current_user",
    "get_current_active_user",
    "get_optional_user",
    "verify_api_key",
    # API Keys
    "generate_api_key",
    "hash_api_key",
    "verify_api_key_hash",
]
