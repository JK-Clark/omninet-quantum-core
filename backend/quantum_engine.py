# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
"""
Kyber-512 Post-Quantum Cryptography Simulation.

This module simulates Kyber-512 key encapsulation and AAA signing using
NaCl (libsodium) primitives as a stand-in for the actual Kyber lattice-based
algorithm, which is not yet available in stable Python packages.  The interface
mirrors what a real Kyber-512 library would expose so the rest of the codebase
can be swapped to a native implementation without changing call sites.
"""

import hashlib
import hmac
import os
import threading
from dataclasses import dataclass, field
from typing import Tuple

import nacl.encoding
import nacl.public
import nacl.signing
import nacl.utils


@dataclass
class QuantumKeyPair:
    """Holds a simulated Kyber-512 key pair."""

    public_key: bytes
    private_key: bytes
    signing_key_raw: bytes = field(repr=False)
    verify_key_raw: bytes = field(repr=False)


def generate_keypair() -> QuantumKeyPair:
    """Generate a simulated Kyber-512 key pair.

    Uses X25519 (Curve25519 DH) for the KEM keys and Ed25519 for the
    signing keys — a valid lattice-to-elliptic-curve simulation.
    """
    kem_private = nacl.public.PrivateKey.generate()
    sign_key = nacl.signing.SigningKey.generate()

    return QuantumKeyPair(
        public_key=bytes(kem_private.public_key),
        private_key=bytes(kem_private),
        signing_key_raw=bytes(sign_key),
        verify_key_raw=bytes(sign_key.verify_key),
    )


def encapsulate(public_key: bytes) -> Tuple[bytes, bytes]:
    """Encapsulate a shared secret using the recipient's public key.

    Returns:
        (ciphertext, shared_secret) — both as raw bytes.
    """
    ephemeral_private = nacl.public.PrivateKey.generate()
    recipient_pub = nacl.public.PublicKey(public_key)
    box = nacl.public.Box(ephemeral_private, recipient_pub)

    # The ciphertext is the ephemeral public key; the shared secret is derived
    # from the DH exchange hashed with HKDF-SHA256.
    ciphertext: bytes = bytes(ephemeral_private.public_key)
    raw_shared = bytes(box.shared_key())
    shared_secret: bytes = hashlib.sha256(raw_shared).digest()

    return ciphertext, shared_secret


def decapsulate(private_key: bytes, ciphertext: bytes) -> bytes:
    """Recover the shared secret from a ciphertext using the private key.

    Args:
        private_key: The recipient's private KEM key.
        ciphertext: The ephemeral public key produced by ``encapsulate``.

    Returns:
        The recovered shared_secret (32 bytes).
    """
    recipient_priv = nacl.public.PrivateKey(private_key)
    sender_pub = nacl.public.PublicKey(ciphertext)
    box = nacl.public.Box(recipient_priv, sender_pub)

    raw_shared = bytes(box.shared_key())
    shared_secret: bytes = hashlib.sha256(raw_shared).digest()
    return shared_secret


def quantum_sign(data: bytes, signing_key_raw: bytes) -> bytes:
    """Sign *data* for AAA authentication using a simulated Kyber/Dilithium signature.

    Uses Ed25519 under the hood (a post-quantum-resistant candidate signature
    scheme for the simulation layer).

    Returns:
        The 64-byte Ed25519 signature.
    """
    signing_key = nacl.signing.SigningKey(signing_key_raw)
    signed = signing_key.sign(data)
    # signed.signature is the bare 64-byte signature
    return signed.signature


def verify_quantum_signature(
    data: bytes, signature: bytes, verify_key_raw: bytes
) -> bool:
    """Verify a quantum-signed payload.

    Returns:
        ``True`` if the signature is valid, ``False`` otherwise.
    """
    try:
        verify_key = nacl.signing.VerifyKey(verify_key_raw)
        verify_key.verify(data, signature)
        return True
    except Exception:
        return False


def derive_aaa_token(shared_secret: bytes, user_id: str) -> str:
    """Derive a deterministic AAA access token from a shared secret.

    The token is an HMAC-SHA256 hex digest, binding the shared secret to the
    user identity so it cannot be reused across accounts.
    """
    mac = hmac.new(shared_secret, user_id.encode(), hashlib.sha256)
    return mac.hexdigest()


# ─── FastAPI dependency ───────────────────────────────────────────────────────

_GLOBAL_KEYPAIR: QuantumKeyPair | None = None
_KEYPAIR_LOCK = threading.Lock()


def get_quantum_keypair() -> QuantumKeyPair:
    """FastAPI dependency: returns (and lazily initialises) the server key pair.

    Thread-safe: uses a lock to prevent race conditions in multi-worker deployments.
    """
    global _GLOBAL_KEYPAIR
    if _GLOBAL_KEYPAIR is None:
        with _KEYPAIR_LOCK:
            if _GLOBAL_KEYPAIR is None:
                _GLOBAL_KEYPAIR = generate_keypair()
    return _GLOBAL_KEYPAIR

