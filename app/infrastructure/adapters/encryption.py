"""AES-256 encryption/decryption for SQL credentials."""

from __future__ import annotations

import base64
import json
import os
from typing import Any, Dict

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.infrastructure.config import settings


def _get_key() -> bytes:
    """Decode the AES key from settings (base64-encoded)."""
    key = base64.b64decode(settings.AES_KEY)
    # Pad or truncate to 32 bytes for AES-256
    if len(key) < 32:
        key = key.ljust(32, b"\0")
    return key[:32]


def encrypt_json(data: Dict[str, Any]) -> str:
    """Encrypt a JSON-serializable dict and return base64-encoded ciphertext.

    Format: base64(nonce + ciphertext)
    """
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce for AES-GCM
    plaintext = json.dumps(data).encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return base64.b64encode(nonce + ciphertext).decode("utf-8")


def decrypt_json(encoded: str) -> Dict[str, Any]:
    """Decrypt base64-encoded ciphertext and return the original dict."""
    key = _get_key()
    aesgcm = AESGCM(key)
    raw = base64.b64decode(encoded)
    nonce = raw[:12]
    ciphertext = raw[12:]
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return json.loads(plaintext.decode("utf-8"))
