"""FastAPI authentication dependencies.

Provides dependency injection for route authentication.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import get_session
from src.database.orm import User, APIKey
from src.auth.jwt import verify_token, TOKEN_TYPE_ACCESS
from src.auth.api_keys import verify_api_key_hash, extract_key_prefix, is_valid_api_key_format

# Bearer token security scheme
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Get the current authenticated user.

    Supports both JWT Bearer tokens and API keys.

    Args:
        credentials: Bearer token credentials.
        x_api_key: Optional API key header.
        session: Database session.

    Returns:
        The authenticated user.

    Raises:
        HTTPException: If authentication fails.
    """
    user = None

    # Try API key first (if provided)
    if x_api_key:
        user = await _authenticate_api_key(x_api_key, session)

    # Try Bearer token
    elif credentials:
        user = await _authenticate_bearer(credentials.credentials, session)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    """Get the current active user.

    Args:
        user: The current authenticated user.

    Returns:
        The user if active.

    Raises:
        HTTPException: If user is not active.
    """
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )
    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_session),
) -> Optional[User]:
    """Get the current user if authenticated, None otherwise.

    This is for endpoints that work with or without authentication.

    Args:
        credentials: Bearer token credentials.
        x_api_key: Optional API key header.
        session: Database session.

    Returns:
        The authenticated user or None.
    """
    try:
        return await get_current_user(credentials, x_api_key, session)
    except HTTPException:
        return None


async def verify_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
    session: AsyncSession = Depends(get_session),
) -> APIKey:
    """Verify an API key and return the key record.

    Args:
        x_api_key: The API key header.
        session: Database session.

    Returns:
        The API key record.

    Raises:
        HTTPException: If API key is invalid.
    """
    if not is_valid_api_key_format(x_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format",
        )

    # Get prefix to narrow down search
    prefix = extract_key_prefix(x_api_key)

    # Find matching keys by prefix
    result = await session.execute(
        select(APIKey).where(
            APIKey.key_prefix == prefix,
            APIKey.is_active == True,
        )
    )
    keys = result.scalars().all()

    # Verify against each matching key
    for key in keys:
        if verify_api_key_hash(x_api_key, key.key_hash):
            # Check expiration
            if key.expires_at and key.expires_at < datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key has expired",
                )

            # Update last used timestamp
            key.last_used_at = datetime.now(timezone.utc)

            return key

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
    )


async def _authenticate_bearer(
    token: str,
    session: AsyncSession,
) -> Optional[User]:
    """Authenticate a bearer token.

    Args:
        token: The JWT token.
        session: Database session.

    Returns:
        The authenticated user or None.
    """
    token_data = verify_token(token, TOKEN_TYPE_ACCESS)
    if not token_data:
        return None

    # Get user from database
    result = await session.execute(
        select(User).where(User.id == token_data.user_id)
    )
    return result.scalar_one_or_none()


async def _authenticate_api_key(
    api_key: str,
    session: AsyncSession,
) -> Optional[User]:
    """Authenticate an API key.

    Args:
        api_key: The API key.
        session: Database session.

    Returns:
        The authenticated user or None.
    """
    if not is_valid_api_key_format(api_key):
        return None

    # Get prefix to narrow down search
    prefix = extract_key_prefix(api_key)

    # Find matching keys by prefix
    result = await session.execute(
        select(APIKey).where(
            APIKey.key_prefix == prefix,
            APIKey.is_active == True,
        )
    )
    keys = result.scalars().all()

    # Verify against each matching key
    for key in keys:
        if verify_api_key_hash(api_key, key.key_hash):
            # Check expiration
            if key.expires_at and key.expires_at < datetime.now(timezone.utc):
                return None

            # Update last used timestamp
            key.last_used_at = datetime.now(timezone.utc)

            # Get user
            result = await session.execute(
                select(User).where(User.id == key.user_id)
            )
            return result.scalar_one_or_none()

    return None


class RequireScopes:
    """Dependency to require specific API key scopes.

    Usage:
        @router.get("/admin", dependencies=[Depends(RequireScopes(["admin"]))])
        def admin_route():
            pass
    """

    def __init__(self, required_scopes: list[str]):
        self.required_scopes = required_scopes

    async def __call__(
        self,
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
        session: AsyncSession = Depends(get_session),
    ) -> bool:
        # JWT tokens have full access
        if credentials and not x_api_key:
            return True

        # API keys need scope verification
        if x_api_key:
            key = await verify_api_key(x_api_key, session)

            # Check if all required scopes are present
            for scope in self.required_scopes:
                if scope not in (key.scopes or []):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"API key missing required scope: {scope}",
                    )

            return True

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
