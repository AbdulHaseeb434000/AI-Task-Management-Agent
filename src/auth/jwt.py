"""JWT token utilities.

Provides token creation and verification for authentication.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from dataclasses import dataclass

from jose import jwt, JWTError

from config.settings import get_settings

settings = get_settings()


# Token types
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


@dataclass
class TokenData:
    """Extracted token data."""
    user_id: uuid.UUID
    email: str
    token_type: str
    exp: datetime
    iat: datetime
    jti: str  # JWT ID for revocation


def create_access_token(
    user_id: uuid.UUID,
    email: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a new access token.

    Args:
        user_id: The user's UUID.
        email: The user's email.
        expires_delta: Optional custom expiration time.

    Returns:
        Encoded JWT access token.
    """
    now = datetime.now(timezone.utc)

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    payload = {
        "sub": str(user_id),
        "email": email,
        "type": TOKEN_TYPE_ACCESS,
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(
    user_id: uuid.UUID,
    email: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a new refresh token.

    Args:
        user_id: The user's UUID.
        email: The user's email.
        expires_delta: Optional custom expiration time.

    Returns:
        Encoded JWT refresh token.
    """
    now = datetime.now(timezone.utc)

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.refresh_token_expire_days)

    payload = {
        "sub": str(user_id),
        "email": email,
        "type": TOKEN_TYPE_REFRESH,
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def verify_token(token: str, expected_type: str = TOKEN_TYPE_ACCESS) -> Optional[TokenData]:
    """Verify and decode a JWT token.

    Args:
        token: The JWT token to verify.
        expected_type: Expected token type (access or refresh).

    Returns:
        TokenData if valid, None otherwise.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        # Validate token type
        token_type = payload.get("type")
        if token_type != expected_type:
            return None

        # Extract data
        user_id = payload.get("sub")
        email = payload.get("email")
        exp = payload.get("exp")
        iat = payload.get("iat")
        jti = payload.get("jti")

        if not all([user_id, email, exp, iat, jti]):
            return None

        return TokenData(
            user_id=uuid.UUID(user_id),
            email=email,
            token_type=token_type,
            exp=datetime.fromtimestamp(exp, tz=timezone.utc),
            iat=datetime.fromtimestamp(iat, tz=timezone.utc),
            jti=jti,
        )

    except JWTError:
        return None
    except (ValueError, TypeError):
        return None


def create_token_pair(user_id: uuid.UUID, email: str) -> dict:
    """Create both access and refresh tokens.

    Args:
        user_id: The user's UUID.
        email: The user's email.

    Returns:
        Dictionary with access_token and refresh_token.
    """
    return {
        "access_token": create_access_token(user_id, email),
        "refresh_token": create_refresh_token(user_id, email),
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }
