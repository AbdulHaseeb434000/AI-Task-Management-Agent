"""Authentication API routes.

Provides endpoints for login, registration, token refresh, and API key management.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import get_session
from src.database.orm import User, APIKey
from src.auth.password import hash_password, verify_password
from src.auth.jwt import (
    create_token_pair,
    verify_token,
    TOKEN_TYPE_REFRESH,
)
from src.auth.api_keys import generate_api_key
from src.auth.dependencies import get_current_active_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ============================================================================
# Request/Response Models
# ============================================================================

class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """User login request."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    """Token refresh request."""
    refresh_token: str


class UserResponse(BaseModel):
    """User response."""
    id: str
    email: str
    name: str
    is_active: bool
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class APIKeyCreateRequest(BaseModel):
    """API key creation request."""
    name: str = Field(min_length=1, max_length=100)
    scopes: list[str] = Field(default_factory=list)
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=365)


class APIKeyResponse(BaseModel):
    """API key response (without the key itself)."""
    id: str
    name: str
    key_prefix: str
    scopes: list[str]
    rate_limit: int
    is_active: bool
    expires_at: Optional[datetime]
    created_at: datetime
    last_used_at: Optional[datetime]


class APIKeyCreateResponse(APIKeyResponse):
    """API key creation response (includes full key, shown once)."""
    key: str  # Full key - shown only on creation


# ============================================================================
# Authentication Routes
# ============================================================================

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Register a new user.

    Args:
        request: Registration data.
        session: Database session.

    Returns:
        Access and refresh tokens.
    """
    # Check if email already exists
    result = await session.execute(
        select(User).where(User.email == request.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create user
    user = User(
        email=request.email,
        name=request.name,
        hashed_password=hash_password(request.password),
        is_active=True,
        is_verified=False,
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)

    # Generate tokens
    tokens = create_token_pair(user.id, user.email)

    return TokenResponse(**tokens)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Login with email and password.

    Args:
        request: Login credentials.
        session: Database session.

    Returns:
        Access and refresh tokens.
    """
    # Find user
    result = await session.execute(
        select(User).where(User.email == request.email)
    )
    user = result.scalar_one_or_none()

    # Verify password
    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Check if active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # Generate tokens
    tokens = create_token_pair(user.id, user.email)

    return TokenResponse(**tokens)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Refresh access token using refresh token.

    Args:
        request: Refresh token.
        session: Database session.

    Returns:
        New access and refresh tokens.
    """
    # Verify refresh token
    token_data = verify_token(request.refresh_token, TOKEN_TYPE_REFRESH)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Get user
    result = await session.execute(
        select(User).where(User.id == token_data.user_id)
    )
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Generate new tokens
    tokens = create_token_pair(user.id, user.email)

    return TokenResponse(**tokens)


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: User = Depends(get_current_active_user),
) -> UserResponse:
    """Get current user profile.

    Args:
        user: Current authenticated user.

    Returns:
        User profile.
    """
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
    )


# ============================================================================
# API Key Routes
# ============================================================================

@router.post("/api-keys", response_model=APIKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    request: APIKeyCreateRequest,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> APIKeyCreateResponse:
    """Create a new API key.

    The full key is returned only once on creation. Store it securely.

    Args:
        request: API key creation request.
        user: Current authenticated user.
        session: Database session.

    Returns:
        API key with the full key shown once.
    """
    # Generate key
    full_key, key_hash, key_prefix = generate_api_key()

    # Calculate expiration
    expires_at = None
    if request.expires_in_days:
        from datetime import timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(days=request.expires_in_days)

    # Create API key record
    api_key = APIKey(
        user_id=user.id,
        name=request.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        scopes=request.scopes,
        expires_at=expires_at,
    )
    session.add(api_key)
    await session.flush()
    await session.refresh(api_key)

    return APIKeyCreateResponse(
        id=str(api_key.id),
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        key=full_key,  # Show full key only once
        scopes=api_key.scopes or [],
        rate_limit=api_key.rate_limit,
        is_active=api_key.is_active,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
    )


@router.get("/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> list[APIKeyResponse]:
    """List all API keys for the current user.

    Args:
        user: Current authenticated user.
        session: Database session.

    Returns:
        List of API keys (without full keys).
    """
    result = await session.execute(
        select(APIKey).where(
            APIKey.user_id == user.id,
            APIKey.revoked_at.is_(None),
        ).order_by(APIKey.created_at.desc())
    )
    keys = result.scalars().all()

    return [
        APIKeyResponse(
            id=str(key.id),
            name=key.name,
            key_prefix=key.key_prefix,
            scopes=key.scopes or [],
            rate_limit=key.rate_limit,
            is_active=key.is_active,
            expires_at=key.expires_at,
            created_at=key.created_at,
            last_used_at=key.last_used_at,
        )
        for key in keys
    ]


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: uuid.UUID,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Revoke an API key.

    Args:
        key_id: The API key ID to revoke.
        user: Current authenticated user.
        session: Database session.
    """
    result = await session.execute(
        select(APIKey).where(
            APIKey.id == key_id,
            APIKey.user_id == user.id,
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    api_key.is_active = False
    api_key.revoked_at = datetime.now(timezone.utc)
