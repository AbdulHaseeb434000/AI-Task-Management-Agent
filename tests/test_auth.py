"""Tests for authentication module."""

import pytest
import uuid
from datetime import datetime, timedelta, timezone

from src.auth.password import hash_password, verify_password, needs_rehash
from src.auth.api_keys import (
    generate_api_key,
    hash_api_key,
    verify_api_key_hash,
    extract_key_prefix,
    is_valid_api_key_format,
)
from src.auth.jwt import (
    create_access_token,
    create_refresh_token,
    verify_token,
    create_token_pair,
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
)


class TestPassword:
    """Tests for password hashing."""

    def test_hash_password(self):
        """Test password hashing."""
        password = "secure_password_123"
        hashed = hash_password(password)

        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt prefix

    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        password = "secure_password_123"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        password = "secure_password_123"
        hashed = hash_password(password)

        assert verify_password("wrong_password", hashed) is False

    def test_different_hashes_for_same_password(self):
        """Test that same password generates different hashes (salt)."""
        password = "secure_password_123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


class TestAPIKeys:
    """Tests for API key utilities."""

    def test_generate_api_key(self):
        """Test API key generation."""
        full_key, key_hash, key_prefix = generate_api_key()

        assert full_key.startswith("sk-")
        assert len(full_key) == 67  # sk- + 64 hex chars
        assert key_prefix.startswith("sk-")
        assert len(key_prefix) == 11  # sk- + 8 chars
        assert len(key_hash) == 64  # SHA-256 hex

    def test_hash_api_key(self):
        """Test API key hashing."""
        key = "sk-" + "a" * 64
        hashed = hash_api_key(key)

        assert len(hashed) == 64
        assert hashed != key

    def test_verify_api_key_hash_correct(self):
        """Test API key verification with correct key."""
        full_key, key_hash, _ = generate_api_key()

        assert verify_api_key_hash(full_key, key_hash) is True

    def test_verify_api_key_hash_incorrect(self):
        """Test API key verification with incorrect key."""
        _, key_hash, _ = generate_api_key()
        wrong_key = "sk-" + "b" * 64

        assert verify_api_key_hash(wrong_key, key_hash) is False

    def test_extract_key_prefix(self):
        """Test prefix extraction."""
        key = "sk-abcd1234efgh5678"
        prefix = extract_key_prefix(key)

        assert prefix == "sk-abcd1234"

    def test_extract_key_prefix_invalid(self):
        """Test prefix extraction with invalid key."""
        prefix = extract_key_prefix("invalid-key")
        assert prefix == ""

    def test_is_valid_api_key_format_valid(self):
        """Test format validation with valid key."""
        full_key, _, _ = generate_api_key()
        assert is_valid_api_key_format(full_key) is True

    def test_is_valid_api_key_format_invalid(self):
        """Test format validation with invalid keys."""
        assert is_valid_api_key_format("invalid") is False
        assert is_valid_api_key_format("sk-tooshort") is False
        assert is_valid_api_key_format("sk-" + "g" * 64) is False  # not hex


class TestJWT:
    """Tests for JWT token utilities."""

    def test_create_access_token(self):
        """Test access token creation."""
        user_id = uuid.uuid4()
        email = "test@example.com"

        token = create_access_token(user_id, email)

        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_refresh_token(self):
        """Test refresh token creation."""
        user_id = uuid.uuid4()
        email = "test@example.com"

        token = create_refresh_token(user_id, email)

        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_access_token(self):
        """Test access token verification."""
        user_id = uuid.uuid4()
        email = "test@example.com"

        token = create_access_token(user_id, email)
        token_data = verify_token(token, TOKEN_TYPE_ACCESS)

        assert token_data is not None
        assert token_data.user_id == user_id
        assert token_data.email == email
        assert token_data.token_type == TOKEN_TYPE_ACCESS

    def test_verify_refresh_token(self):
        """Test refresh token verification."""
        user_id = uuid.uuid4()
        email = "test@example.com"

        token = create_refresh_token(user_id, email)
        token_data = verify_token(token, TOKEN_TYPE_REFRESH)

        assert token_data is not None
        assert token_data.user_id == user_id
        assert token_data.token_type == TOKEN_TYPE_REFRESH

    def test_verify_token_wrong_type(self):
        """Test that token type must match."""
        user_id = uuid.uuid4()
        email = "test@example.com"

        access_token = create_access_token(user_id, email)
        refresh_token = create_refresh_token(user_id, email)

        # Access token should not verify as refresh
        assert verify_token(access_token, TOKEN_TYPE_REFRESH) is None
        # Refresh token should not verify as access
        assert verify_token(refresh_token, TOKEN_TYPE_ACCESS) is None

    def test_verify_invalid_token(self):
        """Test verification of invalid token."""
        assert verify_token("invalid.token.here", TOKEN_TYPE_ACCESS) is None
        assert verify_token("", TOKEN_TYPE_ACCESS) is None

    def test_create_token_pair(self):
        """Test token pair creation."""
        user_id = uuid.uuid4()
        email = "test@example.com"

        pair = create_token_pair(user_id, email)

        assert "access_token" in pair
        assert "refresh_token" in pair
        assert pair["token_type"] == "bearer"
        assert pair["expires_in"] > 0

        # Verify both tokens work
        assert verify_token(pair["access_token"], TOKEN_TYPE_ACCESS) is not None
        assert verify_token(pair["refresh_token"], TOKEN_TYPE_REFRESH) is not None

    def test_access_token_with_custom_expiry(self):
        """Test access token with custom expiry."""
        user_id = uuid.uuid4()
        email = "test@example.com"

        token = create_access_token(user_id, email, expires_delta=timedelta(hours=1))
        token_data = verify_token(token, TOKEN_TYPE_ACCESS)

        assert token_data is not None
        # Expiry should be approximately 1 hour from now
        expected_exp = datetime.now(timezone.utc) + timedelta(hours=1)
        assert abs((token_data.exp - expected_exp).total_seconds()) < 5
