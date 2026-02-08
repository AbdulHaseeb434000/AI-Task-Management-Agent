"""Password hashing utilities.

Uses bcrypt for secure password hashing.
"""

import bcrypt


# Cost factor for bcrypt (12 is a good balance of security and performance)
BCRYPT_ROUNDS = 12


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    Args:
        password: The plain text password.

    Returns:
        The hashed password.
    """
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.

    Args:
        plain_password: The plain text password to verify.
        hashed_password: The hashed password to check against.

    Returns:
        True if password matches, False otherwise.
    """
    try:
        password_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


def needs_rehash(hashed_password: str, target_rounds: int = BCRYPT_ROUNDS) -> bool:
    """Check if a password hash needs to be rehashed.

    This is useful when upgrading hash algorithm parameters.

    Args:
        hashed_password: The current password hash.
        target_rounds: The target number of rounds.

    Returns:
        True if the hash should be regenerated.
    """
    try:
        # Extract the cost factor from the hash
        # bcrypt hash format: $2b$12$...
        parts = hashed_password.split('$')
        if len(parts) >= 3:
            current_rounds = int(parts[2])
            return current_rounds < target_rounds
        return True
    except Exception:
        return True
