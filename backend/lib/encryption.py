"""AES-256-GCM encryption for CV blobs at rest."""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _key_from_settings(key_b64: str) -> bytes:
    raw = base64.b64decode(key_b64.strip())
    if len(raw) != 32:
        raise ValueError("CV_ENCRYPTION_KEY must decode to 32 bytes (AES-256)")
    return raw


def encrypt_bytes(plaintext: bytes, key_b64: str) -> bytes:
    """Return nonce (12 bytes) + ciphertext + tag (GCM)."""
    key = _key_from_settings(key_b64)
    aes = AESGCM(key)
    nonce = os.urandom(12)
    return nonce + aes.encrypt(nonce, plaintext, None)


def decrypt_bytes(blob: bytes, key_b64: str) -> bytes:
    if len(blob) < 12:
        raise ValueError("Invalid encrypted payload")
    key = _key_from_settings(key_b64)
    nonce, ct = blob[:12], blob[12:]
    aes = AESGCM(key)
    return aes.decrypt(nonce, ct, None)
