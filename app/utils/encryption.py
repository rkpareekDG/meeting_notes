"""Encryption utility using AES-256-GCM."""

import base64
import hashlib
import hmac
import os
import secrets
from typing import Tuple

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings


class EncryptionUtil:
    """AES-256-GCM encryption utility."""

    def __init__(self, encryption_key: str | None = None) -> None:
        """Initialize with encryption key."""
        key_string = encryption_key or settings.encryption_key
        # Derive a 32-byte key using SHA-256
        self.key = hashlib.sha256(key_string.encode()).digest()

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext using AES-256-GCM.

        Returns: Base64 encoded string in format: nonce:ciphertext:tag
        """
        nonce = os.urandom(12)  # 96-bit nonce for GCM
        aesgcm = AESGCM(self.key)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)

        # Encode and combine
        nonce_b64 = base64.b64encode(nonce).decode()
        ciphertext_b64 = base64.b64encode(ciphertext).decode()

        return f"{nonce_b64}:{ciphertext_b64}"

    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt ciphertext using AES-256-GCM.

        Args:
            encrypted: Base64 encoded string in format: nonce:ciphertext
        """
        parts = encrypted.split(":")
        if len(parts) != 2:
            raise ValueError("Invalid ciphertext format")

        nonce = base64.b64decode(parts[0])
        ciphertext = base64.b64decode(parts[1])

        aesgcm = AESGCM(self.key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)

        return plaintext.decode()


# Singleton instance
encryption_util = EncryptionUtil()


def encrypt(plaintext: str) -> str:
    """Encrypt plaintext using the singleton encryption utility."""
    return encryption_util.encrypt(plaintext)


def decrypt(encrypted: str) -> str:
    """Decrypt ciphertext using the singleton encryption utility."""
    return encryption_util.decrypt(encrypted)


def hash_string(input_str: str, algorithm: str = "sha256") -> str:
    """Hash a string using the specified algorithm."""
    hasher = hashlib.new(algorithm)
    hasher.update(input_str.encode())
    return hasher.hexdigest()


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_hex(length)


def verify_hmac_signature(
    payload: str,
    signature: str,
    secret: str,
    algorithm: str = "sha256",
) -> bool:
    """
    Verify HMAC signature.

    Args:
        payload: The payload that was signed
        signature: The signature to verify
        secret: The secret key used for signing
        algorithm: Hash algorithm to use

    Returns:
        True if signature is valid
    """
    expected_signature = hmac.new(
        secret.encode(),
        payload.encode(),
        getattr(hashlib, algorithm),
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)
