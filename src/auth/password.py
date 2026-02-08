"""Password hashing utilities.

Uses bcrypt for secure password hashing.
"""

from passlib.context import CryptContext

# Password hashing context
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # Good balance of security and performance
)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    Args:
        password: The plain text password.

    Returns:
        The hashed password.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.

    Args:
        plain_password: The plain text password to verify.
        hashed_password: The hashed password to check against.

    Returns:
        True if password matches, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


def needs_rehash(hashed_password: str) -> bool:
    """Check if a password hash needs to be rehashed.

    This is useful when upgrading hash algorithm parameters.

    Args:
        hashed_password: The current password hash.

    Returns:
        True if the hash should be regenerated.
    """
    return pwd_context.needs_update(hashed_password)
