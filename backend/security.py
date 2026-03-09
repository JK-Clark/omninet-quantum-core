# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
# backend/security.py — Post-quantum cryptography simulation module

"""
Post-Quantum Cryptography Simulation Module
============================================
This module simulates the Kyber-512 Key Encapsulation Mechanism (KEM) using
RSA-2048 with OAEP/SHA-256 as the underlying primitive.  It is intended for
environments where ``liboqs`` (Open Quantum Safe) is not available.

In a production deployment with liboqs, replace the RSA primitives with real
Kyber-512 operations while keeping the same function signatures.

Functions
---------
* :func:`generate_keypair`  — generate a simulated Kyber key pair
* :func:`encrypt`           — encrypt bytes with a public key (RSA-OAEP/SHA-256)
* :func:`decrypt`           — decrypt ciphertext with a private key
* :func:`kyber_hash`        — SHA3-256 hash (simulates Kyber's hash component)
* :func:`generate_session_token` — cryptographically secure 32-byte hex token
"""

import hashlib
import secrets
from typing import Tuple

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


def generate_keypair() -> Tuple[bytes, bytes]:
    """Generate an RSA-2048 key pair that simulates a Kyber-512 KEM key pair.

    Returns:
        A ``(public_key_bytes, private_key_bytes)`` tuple where both elements
        are PEM-encoded bytes.
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    public_key = private_key.public_key()

    private_key_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_key_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return public_key_bytes, private_key_bytes


def encrypt(public_key_bytes: bytes, plaintext: bytes) -> bytes:
    """Encrypt *plaintext* using RSA-OAEP with SHA-256 (Kyber-512 simulation).

    Args:
        public_key_bytes: PEM-encoded RSA-2048 public key.
        plaintext: Raw bytes to encrypt.

    Returns:
        Encrypted ciphertext as raw bytes.
    """
    public_key = serialization.load_pem_public_key(public_key_bytes)
    ciphertext = public_key.encrypt(
        plaintext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return ciphertext


def decrypt(private_key_bytes: bytes, ciphertext: bytes) -> bytes:
    """Decrypt *ciphertext* using RSA-OAEP with SHA-256 (Kyber-512 simulation).

    Args:
        private_key_bytes: PEM-encoded RSA-2048 private key.
        ciphertext: Encrypted bytes returned by :func:`encrypt`.

    Returns:
        Decrypted plaintext as raw bytes.
    """
    private_key = serialization.load_pem_private_key(private_key_bytes, password=None)
    plaintext = private_key.decrypt(
        ciphertext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return plaintext


def kyber_hash(data: bytes) -> str:
    """Compute a SHA3-256 digest of *data* (simulates Kyber's hash component).

    Args:
        data: Raw bytes to hash.

    Returns:
        Hex-encoded SHA3-256 digest string (64 hex characters).
    """
    return hashlib.sha3_256(data).hexdigest()


def generate_session_token() -> str:
    """Generate a cryptographically secure random session token.

    Returns:
        A 64-character hex string derived from 32 random bytes.
    """
    return secrets.token_hex(32)
