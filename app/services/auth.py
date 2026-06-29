"""
services.auth
=============
Utility functions for hashing and verifying passwords using PBKDF2.
"""

import hashlib
import os


def hash_password(password: str) -> str:
    """
    Hash a password using PBKDF2-HMAC-SHA256 with a random salt.
    """
    salt = os.urandom(16)
    pw_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return salt.hex() + ":" + pw_hash.hex()


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify a password against a PBKDF2 hash.
    """
    try:
        salt_hex, hash_hex = hashed.split(":")
        salt = bytes.fromhex(salt_hex)
        pw_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
        return pw_hash.hex() == hash_hex
    except Exception:
        return False
