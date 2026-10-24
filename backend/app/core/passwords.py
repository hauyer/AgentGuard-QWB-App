"""Password hashing for database-backed application users (B9).

Uses PBKDF2-HMAC-SHA-256 from the standard library - no plaintext passwords,
no reversible storage, no new dependency. Stored format:

    pbkdf2_sha256$<iterations>$<salt-hex>$<hash-hex>

Verification is constant-time via hmac.compare_digest.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_ALGORITHM = "pbkdf2_sha256"
DEFAULT_ITERATIONS = 390_000  # OWASP 2023+ guidance for PBKDF2-SHA256
_SALT_BYTES = 16
_KEY_LENGTH = 32


def hash_password(password: str, *, iterations: int = DEFAULT_ITERATIONS) -> str:
    if not password or len(password) > 1024:
        raise ValueError("password must be 1..1024 characters")
    salt = secrets.token_hex(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), iterations, _KEY_LENGTH)
    return f"{_ALGORITHM}${iterations}${salt}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored or not password:
        # Always run one dummy derivation so timing does not reveal whether
        # the account exists in the database.
        hashlib.pbkdf2_hmac("sha256", b"dummy", b"0" * (_SALT_BYTES * 2), 1_000, _KEY_LENGTH)
        return False
    try:
        algorithm, iterations_text, salt_hex, hash_hex = stored.split("$")
        iterations = int(iterations_text)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False
    if algorithm != _ALGORITHM or iterations <= 0 or not expected:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations, len(expected)
    )
    return hmac.compare_digest(digest, expected)


def is_hashed_password(stored: str | None) -> bool:
    """True when the stored value looks like a hash (guards against plaintext)."""
    if not stored:
        return False
    parts = stored.split("$")
    return len(parts) == 4 and parts[0] == _ALGORITHM and parts[2].strip() != ""
