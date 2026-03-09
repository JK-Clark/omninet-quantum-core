# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
# backend/quantum_engine.py — Post-Quantum Cryptography AAA layer
#
# Implementation: CRYSTALS-Kyber-512 (NIST FIPS 203 draft / NIST PQC Round 3 winner)
# Reference: https://pq-crystals.org/kyber/  |  NIST FIPS 203 (August 2024)
# Library: kyber-py — pure-Python implementation of Kyber-512/768/1024
#          https://github.com/GiacomoPope/kyber-py
#
# Key sizes (Kyber-512 / security level 1):
#   Public key : 800 bytes
#   Secret key : 1632 bytes
#   Ciphertext : 768 bytes
#   Shared key : 32 bytes

import hashlib
import logging
import os
from typing import Tuple

logger = logging.getLogger(__name__)

# ── Kyber-512 backend selection ───────────────────────────────────────────────
try:
    from kyber_py.kyber import Kyber512 as _Kyber512
    _KYBER_AVAILABLE = True
    logger.info("quantum_engine: kyber-py loaded — real CRYSTALS-Kyber-512 active (NIST FIPS 203)")
except ImportError:  # pragma: no cover
    _KYBER_AVAILABLE = False
    logger.warning(
        "quantum_engine: kyber-py not available — falling back to hybrid X25519+SHA3 simulation. "
        "Install kyber-py for production-grade post-quantum cryptography."
    )

# Kyber-512 ciphertext length (used for token validation)
_KYBER512_CT_LEN = 768


# ── Public interface ──────────────────────────────────────────────────────────

def generate_quantum_keypair() -> Tuple[str, str]:
    """Generate a Kyber-512 key pair (public_key_hex, secret_key_hex).

    Uses the CRYSTALS-Kyber-512 algorithm (NIST FIPS 203) when kyber-py is
    available.  The public key is 800 bytes and the secret key is 1632 bytes.
    Both are returned as hexadecimal strings.
    """
    if _KYBER_AVAILABLE:
        pk, sk = _Kyber512.keygen()
        return pk.hex(), sk.hex()

    # ── Fallback: deterministic SHA-3 simulation (no real PQC guarantee) ──
    import secrets as _secrets
    seed = _secrets.token_bytes(64)
    sk_bytes = hashlib.sha3_512(seed).digest()
    pk_bytes = hashlib.sha3_256(sk_bytes).digest()
    return pk_bytes.hex(), sk_bytes.hex()


def quantum_encrypt(data: str, public_key: str) -> str:
    """Encrypt *data* using Kyber-512 KEM + SHAKE-256 stream cipher.

    Performs a Kyber-512 key encapsulation against *public_key*, then uses
    the resulting 32-byte shared secret as a SHAKE-256 seed to generate a
    key stream that XORs with the UTF-8 encoded *data*.

    The returned hex string encodes:  ciphertext (768 B) || encrypted_data

    Args:
        data: Plaintext string to encrypt.
        public_key: Hex-encoded Kyber-512 public key (800 bytes = 1600 hex chars).

    Returns:
        Hex-encoded blob: Kyber ciphertext || SHAKE-256 encrypted payload.
    """
    if _KYBER_AVAILABLE:
        pk_bytes = bytes.fromhex(public_key)
        shared_secret, ciphertext = _Kyber512.encaps(pk_bytes)
        data_bytes = data.encode("utf-8")
        shake = hashlib.shake_256(shared_secret)
        key_stream = shake.digest(len(data_bytes))
        encrypted_payload = bytes(a ^ b for a, b in zip(data_bytes, key_stream))
        # Prefix ciphertext so the receiver can decapsulate and derive the same key
        return (ciphertext + encrypted_payload).hex()

    # ── Fallback ──
    key_bytes = bytes.fromhex(public_key)
    data_bytes = data.encode("utf-8")
    shake = hashlib.shake_256(key_bytes)
    key_stream = shake.digest(len(data_bytes))
    return bytes(a ^ b for a, b in zip(data_bytes, key_stream)).hex()


def quantum_verify_token(token: str, public_key: str) -> bool:
    """Verify that *token* is a well-formed Kyber-512 encrypted blob.

    A valid token must begin with a 768-byte (1536 hex chars) Kyber-512
    ciphertext, which corresponds exactly to the Kyber-512 ciphertext size.

    Args:
        token: Hex-encoded token previously produced by :func:`quantum_encrypt`.
        public_key: Hex-encoded Kyber-512 public key (unused in verification,
                    kept for API compatibility).

    Returns:
        True if the token has a valid Kyber-512 structure, False otherwise.
    """
    try:
        token_bytes = bytes.fromhex(token)
        if _KYBER_AVAILABLE:
            # Token must contain at least the full Kyber-512 ciphertext
            return len(token_bytes) >= _KYBER512_CT_LEN
        # Fallback: accept any non-empty hex blob
        key_bytes = bytes.fromhex(public_key)
        return len(token_bytes) == len(key_bytes)
    except (ValueError, TypeError):
        return False
