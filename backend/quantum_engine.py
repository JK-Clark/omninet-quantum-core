# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
# backend/quantum_engine.py — Simulated Kyber-512 AAA layer

import hashlib
import hmac
import os
import secrets
from typing import Tuple


def generate_quantum_keypair() -> Tuple[str, str]:
    """Generate a simulated Kyber-512 key pair (public_key, private_key).

    The simulation uses cryptographically strong random bytes combined with
    SHA-3 (Keccak) to mimic the lattice-based structure of Kyber without
    requiring an external post-quantum library.
    """
    seed = secrets.token_bytes(64)
    private_key_bytes = hashlib.sha3_512(seed).digest()
    public_key_bytes = hashlib.sha3_256(private_key_bytes).digest()
    return public_key_bytes.hex(), private_key_bytes.hex()


def quantum_encrypt(data: str, public_key: str) -> str:
    """Simulate Kyber-512 encapsulation / encryption.

    The ciphertext is produced by XOR-ing the UTF-8 data bytes with a key
    stream derived from the public key via SHAKE-256.  The result is returned
    as a hex string.
    """
    key_bytes = bytes.fromhex(public_key)
    data_bytes = data.encode("utf-8")
    shake = hashlib.shake_256(key_bytes)
    key_stream = shake.digest(len(data_bytes))
    ciphertext = bytes(a ^ b for a, b in zip(data_bytes, key_stream))
    return ciphertext.hex()


def quantum_verify_token(token: str, public_key: str) -> bool:
    """Simulate Kyber-512 decapsulation / token verification.

    A valid simulated token is a hex string whose length equals twice the
    length of the public-key bytes (one ciphertext byte per key byte).
    This mirrors the fixed-size ciphertext of the real Kyber-512 scheme.
    """
    try:
        key_bytes = bytes.fromhex(public_key)
        token_bytes = bytes.fromhex(token)
        # In the simulated scheme the ciphertext length must match the key length
        return len(token_bytes) == len(key_bytes)
    except (ValueError, TypeError):
        return False
